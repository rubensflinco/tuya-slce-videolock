"""Binary sensors — online, doorbell, hijack."""

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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DP_DOORBELL, DP_HIJACK
from .coordinator import SlceVideolockCoordinator
from .device import build_device_info


@dataclass(frozen=True, kw_only=True)
class SlceBinaryDescription(BinarySensorEntityDescription):
    status_key: str = ""
    from_meta_online: bool = False


BINARY_SENSORS: tuple[SlceBinaryDescription, ...] = (
    SlceBinaryDescription(
        key="online",
        name="Online",
        from_meta_online=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cloud-check",
    ),
    SlceBinaryDescription(
        key="doorbell",
        name="Campainha",
        status_key=DP_DOORBELL,
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        icon="mdi:doorbell",
    ),
    SlceBinaryDescription(
        key="hijack",
        name="Alerta de coação",
        status_key=DP_HIJACK,
        device_class=BinarySensorDeviceClass.TAMPER,
        icon="mdi:alert-octagon",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SlceVideolockCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    device_id: str = hass.data[DOMAIN][entry.entry_id]["device_id"]
    async_add_entities(
        [SlceBinarySensor(coordinator, device_id, desc) for desc in BINARY_SENSORS]
    )


class SlceBinarySensor(
    CoordinatorEntity[SlceVideolockCoordinator], BinarySensorEntity
):
    entity_description: SlceBinaryDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SlceVideolockCoordinator,
        device_id: str,
        description: SlceBinaryDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"
        name = coordinator.data.get("name") if coordinator.data else None
        self._attr_device_info = build_device_info(device_id, name)

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None
        if self.entity_description.from_meta_online:
            return bool(self.coordinator.data.get("online"))
        status = self.coordinator.data.get("status") or {}
        value = status.get(self.entity_description.status_key)
        if value is None:
            return None
        return bool(value)
