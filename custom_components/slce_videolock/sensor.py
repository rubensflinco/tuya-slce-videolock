"""Sensor platform — battery + last unlock / alarm (Lock Monitor style).

Sensor naming and DP keys adapted from crestall/ha-tuya-lock-monitor (MIT).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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

from .const import (
    DOMAIN,
    DP_ALARM_LOCK,
    DP_BATTERY,
    DP_UNLOCK_APP,
    DP_UNLOCK_CARD,
    DP_UNLOCK_FINGERPRINT,
    DP_UNLOCK_PASSWORD,
    DP_UNLOCK_TEMPORARY,
)
from .coordinator import SlceVideolockCoordinator
from .entity import SlceCoordinatorEntity


@dataclass(frozen=True, kw_only=True)
class SlceSensorDescription(SensorEntityDescription):
    """Sensor description with optional status DP key."""

    status_key: str = ""
    from_coordinator_attr: str | None = None


SENSORS: tuple[SlceSensorDescription, ...] = (
    SlceSensorDescription(
        key="battery",
        translation_key="battery",
        name="Bateria",
        status_key=DP_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SlceSensorDescription(
        key="unlock_fingerprint",
        translation_key="last_fingerprint_unlock",
        name="Último desbloqueio (digital)",
        status_key=DP_UNLOCK_FINGERPRINT,
        icon="mdi:fingerprint",
    ),
    SlceSensorDescription(
        key="unlock_password",
        translation_key="last_password_unlock",
        name="Último desbloqueio (senha)",
        status_key=DP_UNLOCK_PASSWORD,
        icon="mdi:form-textbox-password",
    ),
    SlceSensorDescription(
        key="unlock_card",
        translation_key="last_card_unlock",
        name="Último desbloqueio (cartão)",
        status_key=DP_UNLOCK_CARD,
        icon="mdi:card-account-details",
    ),
    SlceSensorDescription(
        key="unlock_app",
        translation_key="app_unlocks",
        name="Desbloqueios via app",
        status_key=DP_UNLOCK_APP,
        icon="mdi:cellphone-lock",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SlceSensorDescription(
        key="unlock_temporary",
        translation_key="temporary_code_unlocks",
        name="Desbloqueios código temporário",
        status_key=DP_UNLOCK_TEMPORARY,
        icon="mdi:key-clock",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SlceSensorDescription(
        key="alarm_lock",
        translation_key="last_alarm",
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
    """Set up sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: SlceVideolockCoordinator = data["coordinator"]
    device_id: str = data["device_id"]

    entities: list = [
        SlceStatusSensor(coordinator, device_id, desc) for desc in SENSORS
    ]
    entities.append(SlceLastContactSensor(coordinator, device_id))
    async_add_entities(entities)


class SlceStatusSensor(SlceCoordinatorEntity, SensorEntity):
    """Sensor derived from a Tuya status DP."""

    entity_description: SlceSensorDescription

    def __init__(
        self,
        coordinator: SlceVideolockCoordinator,
        device_id: str,
        description: SlceSensorDescription,
    ) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return (self.coordinator.data.get("status") or {}).get(
            self.entity_description.status_key
        )


class SlceLastContactSensor(SlceCoordinatorEntity, SensorEntity):
    """Timestamp of last successful cloud poll."""

    _attr_name = "Último contato"
    _attr_icon = "mdi:clock-check-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SlceVideolockCoordinator,
        device_id: str,
    ) -> None:
        super().__init__(coordinator, device_id, "last_contact")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_contact

    @property
    def available(self) -> bool:
        return self.coordinator.last_contact is not None
