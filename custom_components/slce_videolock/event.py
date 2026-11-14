"""Event platform — doorbell, unlock methods, alarms.

Uses HA's event entity platform for momentary signals that have no lasting state.
Each event fires once and the state is the timestamp of the last occurrence.
This enables Node-RED / automations to trigger on each press/unlock/alarm.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ALARM_TYPES,
    DOMAIN,
    EVENT_TYPE_ALARM,
    EVENT_TYPE_DOORBELL,
    EVENT_TYPE_HIJACK,
    EVENT_TYPE_UNLOCK,
)
from .coordinator import SlceVideolockCoordinator
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SlceEventDescription(EventEntityDescription):
    """Describe an SL-CE event entity."""

    event_types_list: list[str]


# Unlock method event types (from Tuya DP codes)
UNLOCK_EVENT_TYPES: list[str] = [
    "fingerprint",
    "password",
    "card",
    "face",
    "key",
    "app",
    "temporary",
    "dynamic",
    "phone_remote",
    "finger_vein",
    "hand",
    "voice",
    "offline_password",
    "identity_card",
    "emergency",
    "unknown",
]

EVENT_ENTITIES: tuple[SlceEventDescription, ...] = (
    SlceEventDescription(
        key="doorbell_event",
        name="Campainha",
        device_class=EventDeviceClass.DOORBELL,
        event_types_list=[EVENT_TYPE_DOORBELL],
        icon="mdi:doorbell",
    ),
    SlceEventDescription(
        key="unlock_event",
        name="Desbloqueio",
        device_class=EventDeviceClass.BUTTON,
        event_types_list=UNLOCK_EVENT_TYPES,
        icon="mdi:lock-open",
    ),
    SlceEventDescription(
        key="alarm_event",
        name="Alarme",
        device_class=EventDeviceClass.BUTTON,
        event_types_list=[EVENT_TYPE_ALARM, EVENT_TYPE_HIJACK, *ALARM_TYPES],
        icon="mdi:alarm-light",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up event entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: SlceVideolockCoordinator = data["coordinator"]
    device_id: str = data["device_id"]

    entities = [
        SlceEventEntity(coordinator, device_id, desc)
        for desc in EVENT_ENTITIES
    ]
    async_add_entities(entities)


class SlceEventEntity(EventEntity):
    """Event entity for momentary lock events (doorbell, unlock, alarm)."""

    entity_description: SlceEventDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SlceVideolockCoordinator,
        device_id: str,
        description: SlceEventDescription,
    ) -> None:
        """Initialize the event entity."""
        self._coordinator = coordinator
        self._device_id = device_id
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_event_types = description.event_types_list
        name = coordinator.data.get("name") if coordinator.data else None
        self._attr_device_info = build_device_info(device_id, name)

    async def async_added_to_hass(self) -> None:
        """Register with coordinator once HA entity is ready."""
        await super().async_added_to_hass()
        self._coordinator.register_event_entities([self])

    @callback
    def fire_event(
        self,
        event_type: str,
        event_attributes: dict[str, Any] | None = None,
    ) -> None:
        """Fire an event from the coordinator.

        Called by coordinator when a new event is detected.
        """
        if event_type not in self._attr_event_types:
            _LOGGER.warning(
                "Unknown event type %s for %s, mapping to 'unknown'",
                event_type,
                self.entity_id,
            )
            # For unlock events, map unknown types to "unknown"
            if "unknown" in self._attr_event_types:
                event_type = "unknown"
            else:
                return

        self._trigger_event(event_type, event_attributes)
        self.async_write_ha_state()
        _LOGGER.debug(
            "Fired event %s on %s with attributes %s",
            event_type,
            self.entity_id,
            event_attributes,
        )

    @property
    def event_key(self) -> str:
        """Return the key for coordinator dispatch."""
        return self.entity_description.key
