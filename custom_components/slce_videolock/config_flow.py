"""Config flow for Tuya SL-CE Videolock — friendly form + Cloud validation."""

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
    DEFAULT_DEVICE_ID,
    DEFAULT_DEVICE_NAME,
    DEFAULT_REGION,
    DOMAIN,
    REGION_LABELS,
    TUYA_PROJECT_URL,
)
from .tuya_api import TuyaApiError, TuyaCloudApi

_LOGGER = logging.getLogger(__name__)

# Region aliases from platform.tuya.com → stored OpenAPI key
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


def _user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_ACCESS_ID): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(CONF_ACCESS_SECRET): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(CONF_REGION, default=DEFAULT_REGION): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": key, "label": label}
                        for key, label in REGION_LABELS.items()
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="region",
                )
            ),
        }
    )


async def _validate_input(
    user_input: dict[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    """Validate credentials and that device_id is reachable.

    Returns (errors, extras) where extras may include device_name.
    """
    errors: dict[str, str] = {}
    extras: dict[str, Any] = {}
    api = TuyaCloudApi(
        access_id=user_input[CONF_ACCESS_ID].strip(),
        access_secret=user_input[CONF_ACCESS_SECRET].strip(),
        region=user_input.get(CONF_REGION, DEFAULT_REGION),
    )
    try:
        if not await api.async_test_credentials():
            errors["base"] = "invalid_auth"
            return errors, extras

        device_id = user_input[CONF_DEVICE_ID].strip()
        try:
            info = await api.async_get_device_info(device_id)
            extras[CONF_DEVICE_NAME] = info.get("name") or DEFAULT_DEVICE_NAME
        except TuyaApiError as err:
            _LOGGER.warning("Device info failed during config: %s", err)
            code = str(err.code) if err.code is not None else ""
            if code in {"1106", "2008", "2009"} or "permission" in str(err).lower():
                errors["base"] = "device_not_found"
            else:
                errors["base"] = "cannot_connect"
            return errors, extras

        try:
            remote_ok = await api.async_check_remote_unlock(device_id)
            if not remote_ok:
                _LOGGER.warning(
                    "Remote unlock without password appears disabled for %s — "
                    "enable it in the Smart Life app for unlock to work",
                    device_id,
                )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Remote unlock check skipped: %s", err)

    except ValueError:
        errors["base"] = "invalid_auth"
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Unexpected validation error: %s", err)
        errors["base"] = "cannot_connect"
    finally:
        await api.async_close()

    return errors, extras


class SlceVideolockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tuya SL-CE Videolock."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {
                **user_input,
                CONF_ACCESS_ID: user_input[CONF_ACCESS_ID].strip(),
                CONF_ACCESS_SECRET: user_input[CONF_ACCESS_SECRET].strip(),
                CONF_DEVICE_ID: user_input[CONF_DEVICE_ID].strip(),
                CONF_REGION: _normalize_region(user_input.get(CONF_REGION)),
            }
            errors, extras = await _validate_input(user_input)
            if not errors:
                device_id = user_input[CONF_DEVICE_ID]
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                title_name = extras.get(CONF_DEVICE_NAME) or f"SL-CE ({device_id[-6:]})"
                return self.async_create_entry(
                    title=title_name,
                    data={**user_input, **extras},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _user_schema(),
                {
                    CONF_DEVICE_ID: DEFAULT_DEVICE_ID,
                    CONF_REGION: DEFAULT_REGION,
                },
            ),
            errors=errors,
            description_placeholders={
                "device_hint": DEFAULT_DEVICE_ID,
                "tuya_project_url": TUYA_PROJECT_URL,
            },
        )
