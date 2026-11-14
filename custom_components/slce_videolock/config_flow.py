"""Config flow for SL-CE Videolock."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_DEVICE_ID,
    CONF_REGION,
    DEFAULT_DEVICE_ID,
    DEFAULT_REGION,
    DOMAIN,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_ID): selector.TextSelector(),
        vol.Required(CONF_ACCESS_SECRET): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): selector.TextSelector(),
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): selector.TextSelector(),
    }
)


class SlceVideolockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SL-CE Videolock."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()
            # TODO: validate credentials against Tuya Cloud (ticket API ping)
            return self.async_create_entry(
                title=f"SL-CE ({device_id[-6:]})",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "device_hint": DEFAULT_DEVICE_ID,
            },
        )
