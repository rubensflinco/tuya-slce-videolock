"""Binary sensors — online, doorbell, hijack, lock status.

Binary sensors with pulse-reset support for sticky Cloud values.
The coordinator applies auto-reset after PULSE_RESET_SECONDS for
doorbell and hijack, so they show momentary ON then return to OFF.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

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
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DP_DOORBELL, DP_HIJACK, DP_LOCK_MOTOR_STATE
from .coordinator import SlceVideolockCoordinator
from .device import build_device_info


@dataclass(frozen=True, kw_only=True)
class SlceBinaryDescription(BinarySensorEntityDescription):
    status_key: str = ""
    from_meta_online: bool = False
    from_lock_motor: bool = False
    track_last_changed: bool = False


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
        track_last_changed=True,
    ),
    SlceBinaryDescription(
        key="hijack",
        name="Alerta de coação",
        status_key=DP_HIJACK,
        device_class=BinarySensorDeviceClass.TAMPER,
        icon="mdi:alert-octagon",
        track_last_changed=True,
    ),
    SlceBinaryDescription(
        key="lock_status",
        name="Porta destrancada",
        from_lock_motor=True,
        device_class=BinarySensorDeviceClass.LOCK,
        icon="mdi:door",
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
    """Binary sensor with pulse-reset support for sticky values."""

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
        self._last_on_time: datetime | None = None
        self._last_value: bool | None = None
        name = coordinator.data.get("name") if coordinator.data else None
        self._attr_device_info = build_device_info(device_id, name)

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None

        if self.entity_description.from_meta_online:
            return bool(self.coordinator.data.get("online"))

        if self.entity_description.from_lock_motor:
            # lock_motor_state True = unlocked, False = locked
            status = self.coordinator.data.get("status") or {}
            motor = status.get(DP_LOCK_MOTOR_STATE)
            if motor is None:
                return None
            # BinarySensorDeviceClass.LOCK: on = unlocked
            return bool(motor)

        # Use effective status (with pulse reset applied by coordinator)
        status = self.coordinator.data.get("status") or {}
        value = status.get(self.entity_description.status_key)
        if value is None:
            return None

        current = bool(value)

        # Track last ON time for extra_state_attributes
        if self.entity_description.track_last_changed:
            if current and not self._last_value:
                self._last_on_time = dt_util.utcnow()
            self._last_value = current

        return current

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes with event tracking data."""
        attrs: dict[str, Any] = {}

        if self.entity_description.track_last_changed:
            # Add event count from coordinator
            counts = self.coordinator.data.get("event_counts") or {}
            key = self.entity_description.key
            if key in counts:
                attrs["event_count"] = counts[key]

            # Add last triggered timestamp
            if key == "doorbell":
                ts = self.coordinator.data.get("last_doorbell_ts", 0)
            elif key == "hijack":
                ts = self.coordinator.data.get("last_alarm_ts", 0)
            else:
                ts = 0

            if ts > 0:
                attrs["last_triggered"] = datetime.fromtimestamp(
                    ts / 1000, tz=dt_util.UTC
                ).isoformat()

            if self._last_on_time:
                attrs["last_on_time"] = self._last_on_time.isoformat()

        return attrs if attrs else None
