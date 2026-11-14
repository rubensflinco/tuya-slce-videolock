"""Config flow: credentials → pick lock from Cloud device list."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_REGION,
    DEFAULT_DEVICE_NAME,
    DEFAULT_REGION,
    DOMAIN,
    REGION_LABELS,
    TUYA_PROJECT_URL,
)
from .tuya_api import TuyaApiError, TuyaCloudApi, format_device_option

_LOGGER = logging.getLogger(__name__)

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


class SlceVideolockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Two-step setup: Cloud credentials, then select a lock device."""

    VERSION = 1

    def __init__(self) -> None:
        self._access_id: str = ""
        self._access_secret: str = ""
        self._region: str = DEFAULT_REGION
        self._devices: list[dict[str, Any]] = []

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
                        errors["base"] = "cannot_connect"
                    else:
                        if not self._devices:
                            errors["base"] = "no_compatible_devices"
                        else:
                            return await self.async_step_select_device()
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
        """Step 2: pick a videolock / smart lock from the Cloud account."""
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
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                name = (
                    str(match.get("name") or "").strip()
                    or DEFAULT_DEVICE_NAME
                )
                # Soft-check remote unlock
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
                                "Remote unlock without password appears disabled "
                                "for %s — enable it in Smart Life",
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
                    },
                )

        return self.async_show_form(
            step_id="select_device",
            data_schema=_device_schema(options),
            errors=errors,
            description_placeholders={
                "device_count": str(len(options)),
            },
        )
