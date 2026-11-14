"""Sensor platform — stubs for Lock Monitor-style status."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
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
            SlceBatterySensor(entry, device_id),
        ]
    )


class SlceBatterySensor(SensorEntity):
    """Battery % (DP residual_electricity) — wire polling like Lock Monitor."""

    _attr_has_entity_name = True
    _attr_name = "Bateria"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_value = None

    def __init__(self, entry: ConfigEntry, device_id: str) -> None:
        self._attr_unique_id = f"{device_id}_battery"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name="Fechadura Inteligente SL-CE (Wi-Fi)",
            manufacturer="Novadigital / Tuya",
            model="SL-CE Elegance (videolock)",
        )
