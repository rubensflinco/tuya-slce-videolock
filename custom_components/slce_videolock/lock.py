"""Lock platform — stub until Smart Lock ticket API is wired."""

from __future__ import annotations

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_DEVICE_ID, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lock entity."""
    device_id = entry.data[CONF_DEVICE_ID]
    async_add_entities([SlceVideolockLock(entry, device_id)])


class SlceVideolockLock(LockEntity):
    """Represent the SL-CE door lock (Cloud ticket unlock — TBD)."""

    _attr_has_entity_name = True
    _attr_name = "Destrancar"
    _attr_is_locked = True

    def __init__(self, entry: ConfigEntry, device_id: str) -> None:
        self._entry = entry
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_lock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name="Fechadura Inteligente SL-CE (Wi-Fi)",
            manufacturer="Novadigital / Tuya",
            model="SL-CE Elegance (videolock)",
        )

    async def async_unlock(self, **kwargs) -> None:
        """Unlock — implement via Smart Lock ticket API (see tuya-smart-lock)."""
        raise NotImplementedError(
            "Wire Cloud ticket unlock from nicolasglg/tuya-smart-lock"
        )

    async def async_lock(self, **kwargs) -> None:
        """Lock — implement via Smart Lock ticket API."""
        raise NotImplementedError(
            "Wire Cloud ticket lock from nicolasglg/tuya-smart-lock"
        )
