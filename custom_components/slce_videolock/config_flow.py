"""Config flow: credentials → lock → unlock PIN → poll interval → snapshot retention."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_REGION,
    CONF_SNAPSHOT_RETENTION_DAYS,
    CONF_UNLOCK_PIN,
    CONF_UNLOCK_PIN_CONFIRM,
    CONF_UNLOCK_PIN_HASH,
    CONF_UNLOCK_PIN_SALT,
    CONF_UPDATE_INTERVAL,
    DEFAULT_DEVICE_NAME,
    DEFAULT_REGION,
    DEFAULT_SNAPSHOT_RETENTION_DAYS,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
    MAX_SNAPSHOT_RETENTION_DAYS,
    MAX_UPDATE_INTERVAL_SECONDS,
    MIN_SNAPSHOT_RETENTION_DAYS,
    MIN_UPDATE_INTERVAL_SECONDS,
    REGION_LABELS,
    TUYA_PROJECT_URL,
    clamp_retention_days,
)
from .pin import hash_unlock_pin, is_valid_unlock_pin
from .tuya_api import TuyaApiError, TuyaCloudApi, format_device_option

_LOGGER = logging.getLogger(__name__)


def _clamp_update_interval(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_UPDATE_INTERVAL_SECONDS
    return max(
        MIN_UPDATE_INTERVAL_SECONDS,
        min(MAX_UPDATE_INTERVAL_SECONDS, value),
    )


_REGION_ALIASES: dict[str, str] = {
    "ay": "cn",
    "az": "us",
    "america": "us",
    "americas": "us",
    "europe": "eu",
    "china": "cn",
    "india": "in",
}


def _normalize_region(raw: str | None) -> str:
    key = (raw or DEFAULT_REGION).strip().lower()
    key = _REGION_ALIASES.get(key, key)
    if key not in REGION_LABELS:
        return DEFAULT_REGION
    return key


def _credentials_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_ACCESS_ID): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(CONF_ACCESS_SECRET): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_REGION, default=DEFAULT_REGION): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": key, "label": label}
                        for key, label in REGION_LABELS.items()
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _device_schema(options: list[dict[str, str]]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_DEVICE_ID): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _manual_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_DEVICE_ID): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
        }
    )


def _unlock_pin_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_UNLOCK_PIN): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_UNLOCK_PIN_CONFIRM): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


def _update_interval_schema(default: int) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_UPDATE_INTERVAL, default=default): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_UPDATE_INTERVAL_SECONDS,
                    max=MAX_UPDATE_INTERVAL_SECONDS,
                    step=1,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _snapshot_retention_schema(default: int) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_SNAPSHOT_RETENTION_DAYS, default=default
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SNAPSHOT_RETENTION_DAYS,
                    max=MAX_SNAPSHOT_RETENTION_DAYS,
                    step=1,
                    unit_of_measurement="d",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _options_schema(interval: int, retention: int) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_UPDATE_INTERVAL, default=interval
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_UPDATE_INTERVAL_SECONDS,
                    max=MAX_UPDATE_INTERVAL_SECONDS,
                    step=1,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SNAPSHOT_RETENTION_DAYS, default=retention
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SNAPSHOT_RETENTION_DAYS,
                    max=MAX_SNAPSHOT_RETENTION_DAYS,
                    step=1,
                    unit_of_measurement="d",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


class SlceVideolockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Credentials, then select lock — or type Device ID if discovery is empty."""

    VERSION = 1

    def __init__(self) -> None:
        self._access_id: str = ""
        self._access_secret: str = ""
        self._region: str = DEFAULT_REGION
        self._devices: list[dict[str, Any]] = []
        self._device_id: str = ""
        self._device_name: str = DEFAULT_DEVICE_NAME
        self._pin_salt: str = ""
        self._pin_hash: str = ""
        self._update_interval: int = DEFAULT_UPDATE_INTERVAL_SECONDS
        self._snapshot_retention_days: int = DEFAULT_SNAPSHOT_RETENTION_DAYS

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Expose poll-interval + snapshot retention options (PIN stays immutable)."""
        return SlceVideolockOptionsFlow()

    async def async_step_user(self, user_input: dict | None = None):
        """Step 1: Access ID, Secret and region."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._access_id = user_input[CONF_ACCESS_ID].strip()
            self._access_secret = user_input[CONF_ACCESS_SECRET].strip()
            self._region = _normalize_region(user_input.get(CONF_REGION))

            api = TuyaCloudApi(
                access_id=self._access_id,
                access_secret=self._access_secret,
                region=self._region,
            )
            try:
                if not await api.async_test_credentials():
                    errors["base"] = "invalid_auth"
                else:
                    try:
                        self._devices = await api.async_list_lock_devices()
                    except (TuyaApiError, ConnectionError, OSError) as err:
                        _LOGGER.warning("Device list failed: %s", err)
                        # Still allow manual Device ID entry
                        self._devices = []
                        return await self.async_step_manual_device()
                    if self._devices:
                        return await self.async_step_select_device()
                    return await self.async_step_manual_device()
            finally:
                await api.async_close()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _credentials_schema(),
                {CONF_REGION: DEFAULT_REGION},
            ),
            errors=errors,
            description_placeholders={
                "tuya_project_url": TUYA_PROJECT_URL,
            },
        )

    async def async_step_select_device(self, user_input: dict | None = None):
        """Step 2a: pick a videolock / smart lock from Cloud discovery."""
        errors: dict[str, str] = {}
        options = [
            {"value": str(d["id"]), "label": format_device_option(d)}
            for d in self._devices
            if d.get("id")
        ]

        if user_input is not None:
            device_id = str(user_input[CONF_DEVICE_ID]).strip()
            match = next(
                (d for d in self._devices if str(d.get("id")) == device_id),
                None,
            )
            if match is None:
                errors["base"] = "device_not_found"
            else:
                name = str(match.get("name") or "").strip() or DEFAULT_DEVICE_NAME
                self._device_id = device_id
                self._device_name = name
                return await self.async_step_unlock_pin()

        return self.async_show_form(
            step_id="select_device",
            data_schema=_device_schema(options),
            errors=errors,
            description_placeholders={
                "device_count": str(len(options)),
            },
        )

    async def async_step_manual_device(self, user_input: dict | None = None):
        """Step 2b: type Device ID when Cloud list is empty / filtered out."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = str(user_input[CONF_DEVICE_ID]).strip()
            if not device_id:
                errors[CONF_DEVICE_ID] = "device_not_found"
            else:
                api = TuyaCloudApi(
                    access_id=self._access_id,
                    access_secret=self._access_secret,
                    region=self._region,
                )
                name = DEFAULT_DEVICE_NAME
                try:
                    try:
                        info = await api.async_get_device_info(device_id)
                        name = str(info.get("name") or "").strip() or name
                    except TuyaApiError as err:
                        _LOGGER.warning("Manual device lookup failed: %s", err)
                        code = str(err.code) if err.code is not None else ""
                        if code in {"1106", "2008", "2009"}:
                            errors["base"] = "device_not_found"
                        else:
                            errors["base"] = "cannot_connect"
                finally:
                    await api.async_close()
                if not errors:
                    self._device_id = device_id
                    self._device_name = name
                    return await self.async_step_unlock_pin()

        return self.async_show_form(
            step_id="manual_device",
            data_schema=_manual_schema(),
            errors=errors,
            description_placeholders={
                "tuya_project_url": TUYA_PROJECT_URL,
            },
        )

    async def async_step_unlock_pin(self, user_input: dict | None = None):
        """Step 3: set immutable 4-digit remote unlock PIN (hashed at rest)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            pin = str(user_input.get(CONF_UNLOCK_PIN) or "").strip()
            confirm = str(user_input.get(CONF_UNLOCK_PIN_CONFIRM) or "").strip()
            if not is_valid_unlock_pin(pin):
                errors[CONF_UNLOCK_PIN] = "invalid_pin"
            elif pin != confirm:
                errors[CONF_UNLOCK_PIN_CONFIRM] = "pin_mismatch"
            else:
                salt, digest = hash_unlock_pin(pin)
                self._pin_salt = salt
                self._pin_hash = digest
                return await self.async_step_polling()

        return self.async_show_form(
            step_id="unlock_pin",
            data_schema=_unlock_pin_schema(),
            errors=errors,
        )

    async def async_step_polling(self, user_input: dict | None = None):
        """Step 4: cloud poll interval (default 60s, min 1s)."""
        if user_input is not None:
            self._update_interval = _clamp_update_interval(
                user_input.get(CONF_UPDATE_INTERVAL)
            )
            return await self.async_step_snapshots()

        return self.async_show_form(
            step_id="polling",
            data_schema=_update_interval_schema(DEFAULT_UPDATE_INTERVAL_SECONDS),
            description_placeholders={
                "default_seconds": str(DEFAULT_UPDATE_INTERVAL_SECONDS),
                "min_seconds": str(MIN_UPDATE_INTERVAL_SECONDS),
                "max_seconds": str(MAX_UPDATE_INTERVAL_SECONDS),
            },
        )

    async def async_step_snapshots(self, user_input: dict | None = None):
        """Step 5: doorbell photo retention (default 30 days)."""
        if user_input is not None:
            self._snapshot_retention_days = clamp_retention_days(
                user_input.get(CONF_SNAPSHOT_RETENTION_DAYS)
            )
            return await self._async_finish(
                self._device_id,
                self._device_name,
                pin_salt=self._pin_salt,
                pin_hash=self._pin_hash,
                update_interval=self._update_interval,
                snapshot_retention_days=self._snapshot_retention_days,
            )

        return self.async_show_form(
            step_id="snapshots",
            data_schema=_snapshot_retention_schema(DEFAULT_SNAPSHOT_RETENTION_DAYS),
            description_placeholders={
                "default_days": str(DEFAULT_SNAPSHOT_RETENTION_DAYS),
                "min_days": str(MIN_SNAPSHOT_RETENTION_DAYS),
                "max_days": str(MAX_SNAPSHOT_RETENTION_DAYS),
            },
        )

    async def _async_finish(
        self,
        device_id: str,
        name: str,
        *,
        pin_salt: str,
        pin_hash: str,
        update_interval: int,
        snapshot_retention_days: int,
    ):
        """Create config entry after unique-id checks + soft remote-unlock warn."""
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()

        api = TuyaCloudApi(
            access_id=self._access_id,
            access_secret=self._access_secret,
            region=self._region,
        )
        try:
            try:
                remote_ok = await api.async_check_remote_unlock(device_id)
                if not remote_ok:
                    _LOGGER.warning(
                        "Remote unlock without password appears disabled for %s",
                        device_id,
                    )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Remote unlock check skipped: %s", err)
        finally:
            await api.async_close()

        return self.async_create_entry(
            title=name,
            data={
                CONF_ACCESS_ID: self._access_id,
                CONF_ACCESS_SECRET: self._access_secret,
                CONF_REGION: self._region,
                CONF_DEVICE_ID: device_id,
                CONF_DEVICE_NAME: name,
                CONF_UNLOCK_PIN_SALT: pin_salt,
                CONF_UNLOCK_PIN_HASH: pin_hash,
            },
            options={
                CONF_UPDATE_INTERVAL: update_interval,
                CONF_SNAPSHOT_RETENTION_DAYS: snapshot_retention_days,
            },
        )


class SlceVideolockOptionsFlow(config_entries.OptionsFlow):
    """Allow changing poll interval and snapshot retention (not the unlock PIN)."""

    async def async_step_init(self, user_input: dict | None = None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_UPDATE_INTERVAL: _clamp_update_interval(
                        user_input.get(CONF_UPDATE_INTERVAL)
                    ),
                    CONF_SNAPSHOT_RETENTION_DAYS: clamp_retention_days(
                        user_input.get(CONF_SNAPSHOT_RETENTION_DAYS)
                    ),
                },
            )

        current_interval = _clamp_update_interval(
            self.config_entry.options.get(
                CONF_UPDATE_INTERVAL,
                self.config_entry.data.get(
                    CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS
                ),
            )
        )
        current_retention = clamp_retention_days(
            self.config_entry.options.get(
                CONF_SNAPSHOT_RETENTION_DAYS,
                self.config_entry.data.get(
                    CONF_SNAPSHOT_RETENTION_DAYS, DEFAULT_SNAPSHOT_RETENTION_DAYS
                ),
            )
        )
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(current_interval, current_retention),
            description_placeholders={
                "default_seconds": str(DEFAULT_UPDATE_INTERVAL_SECONDS),
                "min_seconds": str(MIN_UPDATE_INTERVAL_SECONDS),
                "max_seconds": str(MAX_UPDATE_INTERVAL_SECONDS),
                "default_days": str(DEFAULT_SNAPSHOT_RETENTION_DAYS),
                "min_days": str(MIN_SNAPSHOT_RETENTION_DAYS),
                "max_days": str(MAX_SNAPSHOT_RETENTION_DAYS),
            },
        )
