"""Sensor platform — battery and last_* unlock status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DP_ALARM_LOCK,
    DP_BATTERY,
    DP_UNLOCK_APP,
    DP_UNLOCK_CARD,
    DP_UNLOCK_FINGERPRINT,
    DP_UNLOCK_PASSWORD,
    DP_UNLOCK_REQUEST,
    DP_UNLOCK_TEMPORARY,
)
from .coordinator import SlceVideolockCoordinator
from .device import build_device_info


@dataclass(frozen=True, kw_only=True)
class SlceSensorDescription(SensorEntityDescription):
    status_key: str = ""


SENSORS: tuple[SlceSensorDescription, ...] = (
    SlceSensorDescription(
        key="battery",
        name="Bateria",
        status_key=DP_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SlceSensorDescription(
        key="unlock_fingerprint",
        name="Última digital",
        status_key=DP_UNLOCK_FINGERPRINT,
        icon="mdi:fingerprint",
    ),
    SlceSensorDescription(
        key="unlock_password",
        name="Última senha",
        status_key=DP_UNLOCK_PASSWORD,
        icon="mdi:form-textbox-password",
    ),
    SlceSensorDescription(
        key="unlock_card",
        name="Último cartão",
        status_key=DP_UNLOCK_CARD,
        icon="mdi:card-account-details",
    ),
    SlceSensorDescription(
        key="unlock_app",
        name="Aberturas pelo app",
        status_key=DP_UNLOCK_APP,
        icon="mdi:cellphone-lock",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SlceSensorDescription(
        key="unlock_temporary",
        name="Códigos temporários",
        status_key=DP_UNLOCK_TEMPORARY,
        icon="mdi:key-clock",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SlceSensorDescription(
        key="unlock_request",
        name="Pedidos de abertura",
        status_key=DP_UNLOCK_REQUEST,
        icon="mdi:door-open",
    ),
    SlceSensorDescription(
        key="alarm_lock",
        name="Último alarme",
        status_key=DP_ALARM_LOCK,
        icon="mdi:alarm-light",
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
        [SlceSensor(coordinator, device_id, desc) for desc in SENSORS]
    )


class SlceSensor(CoordinatorEntity[SlceVideolockCoordinator], SensorEntity):
    """Sensor backed by a Tuya status DP."""

    entity_description: SlceSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SlceVideolockCoordinator,
        device_id: str,
        description: SlceSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"
        name = coordinator.data.get("name") if coordinator.data else None
        self._attr_device_info = build_device_info(device_id, name)

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status") or {}
        return status.get(self.entity_description.status_key)
