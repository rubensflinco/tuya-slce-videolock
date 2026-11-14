"""Sensor platform — battery, unlock methods, alarms, event counters.

Enhanced sensors with:
1. All unlock method types (face, fingerprint, card, password, key, etc.)
2. Event counters that increment even when the same value repeats
3. Timestamps of last events for automation triggers
4. Alarm history with count tracking
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    DP_ALARM_LOCK,
    DP_BATTERY,
    DP_UNLOCK_APP,
    DP_UNLOCK_CARD,
    DP_UNLOCK_DYNAMIC,
    DP_UNLOCK_FACE,
    DP_UNLOCK_FINGERPRINT,
    DP_UNLOCK_KEY,
    DP_UNLOCK_PASSWORD,
    DP_UNLOCK_PHONE_REMOTE,
    DP_UNLOCK_REQUEST,
    DP_UNLOCK_TEMPORARY,
)
from .coordinator import SlceVideolockCoordinator
from .device import build_device_info


@dataclass(frozen=True, kw_only=True)
class SlceSensorDescription(SensorEntityDescription):
    status_key: str = ""
    from_event_count: str = ""  # Key in coordinator.event_counts
    from_event_timestamp: str = ""  # Key for timestamp sensor


SENSORS: tuple[SlceSensorDescription, ...] = (
    # === Core sensors ===
    SlceSensorDescription(
        key="battery",
        name="Bateria",
        status_key=DP_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # === Unlock method sensors (last value) ===
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
        key="unlock_face",
        name="Último reconhecimento facial",
        status_key=DP_UNLOCK_FACE,
        icon="mdi:face-recognition",
    ),
    SlceSensorDescription(
        key="unlock_key",
        name="Última chave mecânica",
        status_key=DP_UNLOCK_KEY,
        icon="mdi:key",
    ),
    SlceSensorDescription(
        key="unlock_phone_remote",
        name="Último desbloqueio remoto",
        status_key=DP_UNLOCK_PHONE_REMOTE,
        icon="mdi:cellphone-key",
    ),
    SlceSensorDescription(
        key="unlock_dynamic",
        name="Última senha dinâmica",
        status_key=DP_UNLOCK_DYNAMIC,
        icon="mdi:dialpad",
    ),
    # === Counter sensors ===
    SlceSensorDescription(
        key="unlock_app",
        name="Aberturas pelo app",
        status_key=DP_UNLOCK_APP,
        icon="mdi:cellphone-lock",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SlceSensorDescription(
        key="unlock_temporary",
        name="Códigos temporários usados",
        status_key=DP_UNLOCK_TEMPORARY,
        icon="mdi:key-clock",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SlceSensorDescription(
        key="unlock_request",
        name="Pedidos de abertura pendentes",
        status_key=DP_UNLOCK_REQUEST,
        icon="mdi:door-open",
    ),
    # === Alarm sensor ===
    SlceSensorDescription(
        key="alarm_lock",
        name="Último alarme",
        status_key=DP_ALARM_LOCK,
        icon="mdi:alarm-light",
    ),
    # === Event count sensors (from coordinator tracking) ===
    SlceSensorDescription(
        key="doorbell_count",
        name="Total de toques campainha",
        from_event_count="doorbell",
        icon="mdi:doorbell",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SlceSensorDescription(
        key="alarm_count",
        name="Total de alarmes",
        from_event_count="alarm",
        icon="mdi:alarm-light",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SlceSensorDescription(
        key="unlock_count",
        name="Total de desbloqueios",
        from_event_count="unlock",
        icon="mdi:lock-open-check",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # === Timestamp sensors (for automation triggers on repeated values) ===
    SlceSensorDescription(
        key="last_doorbell_time",
        name="Última campainha",
        from_event_timestamp="doorbell",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:doorbell",
    ),
    SlceSensorDescription(
        key="last_alarm_time",
        name="Último alarme (hora)",
        from_event_timestamp="alarm",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:alarm-light",
    ),
    SlceSensorDescription(
        key="last_unlock_time",
        name="Último desbloqueio (hora)",
        from_event_timestamp="unlock",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:lock-open",
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
    """Sensor backed by a Tuya status DP or coordinator event tracking."""

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
        self._last_value: Any = None
        self._last_change_time: datetime | None = None
        name = coordinator.data.get("name") if coordinator.data else None
        self._attr_device_info = build_device_info(device_id, name)

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None

        desc = self.entity_description

        # Event count sensor
        if desc.from_event_count:
            counts = self.coordinator.data.get("event_counts") or {}
            return counts.get(desc.from_event_count, 0)

        # Timestamp sensor
        if desc.from_event_timestamp:
            ts_key = f"last_{desc.from_event_timestamp}_ts"
            ts = self.coordinator.data.get(ts_key, 0)
            if ts > 0:
                return datetime.fromtimestamp(ts / 1000, tz=dt_util.UTC)
            return None

        # Status DP sensor
        status = self.coordinator.data.get("status") or {}
        value = status.get(desc.status_key)

        # Track changes for extra attributes
        if value != self._last_value:
            self._last_value = value
            self._last_change_time = dt_util.utcnow()

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes with change tracking."""
        attrs: dict[str, Any] = {}
        desc = self.entity_description

        # For DP-based sensors, add last change time
        if desc.status_key and self._last_change_time:
            attrs["last_changed"] = self._last_change_time.isoformat()

        # For alarm sensor, add alarm count
        if desc.key == "alarm_lock":
            counts = self.coordinator.data.get("event_counts") or {}
            attrs["total_alarms"] = counts.get("alarm", 0)

        # For unlock method sensors, add event count and timestamp
        if desc.status_key and desc.status_key.startswith("unlock_"):
            counts = self.coordinator.data.get("event_counts") or {}
            attrs["total_unlocks"] = counts.get("unlock", 0)
            ts = self.coordinator.data.get("last_unlock_ts", 0)
            if ts > 0:
                attrs["last_unlock_time"] = datetime.fromtimestamp(
                    ts / 1000, tz=dt_util.UTC
                ).isoformat()

        return attrs if attrs else None
