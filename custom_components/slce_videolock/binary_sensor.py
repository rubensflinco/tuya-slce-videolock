"""Binary sensors — stubs (doorbell, online, …)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_DEVICE_ID, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device_id = entry.data[CONF_DEVICE_ID]
    async_add_entities(
        [
            SlceOnlineBinary(entry, device_id),
            SlceDoorbellBinary(entry, device_id),
        ]
    )


class _SlceBinary(BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, device_id: str, key: str) -> None:
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name="Fechadura Inteligente SL-CE (Wi-Fi)",
            manufacturer="Novadigital / Tuya",
            model="SL-CE Elegance (videolock)",
        )
        self._attr_is_on = None


class SlceOnlineBinary(_SlceBinary):
    _attr_name = "Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, device_id: str) -> None:
        super().__init__(device_id, "online")


class SlceDoorbellBinary(_SlceBinary):
    _attr_name = "Campainha"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, entry: ConfigEntry, device_id: str) -> None:
        super().__init__(device_id, "doorbell")
