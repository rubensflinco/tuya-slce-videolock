"""Binary sensors — online + doorbell (+ optional hijack).

Patterns adapted from crestall/ha-tuya-lock-monitor (MIT).
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DP_DOORBELL
from .coordinator import SlceVideolockCoordinator
from .entity import SlceCoordinatorEntity


@dataclass(frozen=True, kw_only=True)
class SlceBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor with status key or special online flag."""

    status_key: str = ""
    online_flag: bool = False


BINARY_SENSORS: tuple[SlceBinaryDescription, ...] = (
    SlceBinaryDescription(
        key="online",
        name="Online",
        translation_key="online",
        online_flag=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cloud-check",
    ),
    SlceBinaryDescription(
        key="doorbell",
        name="Campainha",
        translation_key="doorbell",
        status_key=DP_DOORBELL,
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        icon="mdi:doorbell",
    ),
    SlceBinaryDescription(
        key="hijack",
        name="Alerta de coação",
        translation_key="hijack",
        status_key="hijack",
        device_class=BinarySensorDeviceClass.TAMPER,
        icon="mdi:alert-octagon",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: SlceVideolockCoordinator = data["coordinator"]
    device_id: str = data["device_id"]
    async_add_entities(
        SlceBinarySensor(coordinator, device_id, desc) for desc in BINARY_SENSORS
    )


class SlceBinarySensor(SlceCoordinatorEntity, BinarySensorEntity):
    """Binary sensor from coordinator data."""

    entity_description: SlceBinaryDescription

    def __init__(
        self,
        coordinator: SlceVideolockCoordinator,
        device_id: str,
        description: SlceBinaryDescription,
    ) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        if self.entity_description.online_flag:
            value = self.coordinator.data.get("online")
        else:
            value = (self.coordinator.data.get("status") or {}).get(
                self.entity_description.status_key
            )
        if value is None:
            return None
        return bool(value)
