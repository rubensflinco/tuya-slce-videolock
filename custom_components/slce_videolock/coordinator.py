"""Cloud-polling coordinator for SL-CE status DPs + event detection.

Enhanced coordinator that:
1. Polls status DPs every UPDATE_INTERVAL_SECONDS (15s)
2. Fetches recent event logs to detect new unlock/alarm events
3. Fires HA event entities for doorbell, unlock methods, alarms
4. Tracks last event timestamps to avoid duplicate firing
5. Provides pulse reset signals for sticky binary sensors
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ALL_UNLOCK_DPS,
    DEVICE_NAME,
    DOMAIN,
    DP_ALARM_LOCK,
    DP_DOORBELL,
    DP_HIJACK,
    EVENT_TYPE_ALARM,
    EVENT_TYPE_DOORBELL,
    EVENT_TYPE_HIJACK,
    PULSE_RESET_SECONDS,
    UPDATE_INTERVAL_SECONDS,
)
from .tuya_api import TuyaCloudApi

if TYPE_CHECKING:
    from .event import SlceEventEntity

_LOGGER = logging.getLogger(__name__)


def _extract_unlock_method(dp_code: str) -> str:
    """Convert DP code like 'unlock_fingerprint' to event type 'fingerprint'."""
    if dp_code.startswith("unlock_"):
        return dp_code[7:]  # Remove 'unlock_' prefix
    return dp_code


class SlceVideolockCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll device info + status from Tuya Cloud + detect events."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: TuyaCloudApi,
        device_id: str,
    ) -> None:
        self.api = api
        self.device_id = device_id
        self._event_entities: dict[str, "SlceEventEntity"] = {}
        self._last_event_timestamp_ms: int = 0
        self._last_status_snapshot: dict[str, Any] = {}
        self._pending_resets: dict[str, asyncio.TimerHandle | None] = {}
        # Track event counts for sensors (even if same value repeats)
        self._event_counts: dict[str, int] = {
            "doorbell": 0,
            "alarm": 0,
            "unlock": 0,
            "hijack": 0,
        }
        self._last_doorbell_ts: int = 0
        self._last_alarm_ts: int = 0
        self._last_unlock_ts: int = 0
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )

    def register_event_entities(self, entities: list["SlceEventEntity"]) -> None:
        """Register event entities for dispatch."""
        for entity in entities:
            self._event_entities[entity.event_key] = entity

    @callback
    def _schedule_pulse_reset(self, dp_key: str) -> None:
        """Schedule a reset of a sticky DP after PULSE_RESET_SECONDS.

        This handles Cloud sticky values like doorbell=true that never clear.
        After the pulse window, we mark the DP as 'pulsed' in our snapshot.
        """
        # Cancel any pending reset for this key
        if dp_key in self._pending_resets:
            handle = self._pending_resets.pop(dp_key, None)
            if handle:
                handle.cancel()

        @callback
        def _do_reset(_now: Any) -> None:
            self._pending_resets.pop(dp_key, None)
            # Mark as reset in our snapshot so binary_sensor sees False
            if dp_key in self._last_status_snapshot:
                self._last_status_snapshot[dp_key] = False
                _LOGGER.debug("Pulse reset: %s → False", dp_key)
                # Trigger coordinator listeners to update entities
                self.async_set_updated_data(self.data)

        self._pending_resets[dp_key] = async_call_later(
            self.hass, PULSE_RESET_SECONDS, _do_reset
        )

    def _detect_status_changes(
        self, old_status: dict[str, Any], new_status: dict[str, Any]
    ) -> None:
        """Detect changes in status DPs and fire events accordingly."""
        now_ms = int(time.time() * 1000)

        # Doorbell: fire event on any true value (even if was already true)
        doorbell_val = new_status.get(DP_DOORBELL)
        if doorbell_val is True:
            # Only fire if this is a new press (not the same stuck value)
            old_val = old_status.get(DP_DOORBELL)
            if old_val is not True or (now_ms - self._last_doorbell_ts > 5000):
                self._last_doorbell_ts = now_ms
                self._event_counts["doorbell"] += 1
                self._fire_event("doorbell_event", EVENT_TYPE_DOORBELL)
                _LOGGER.info("Doorbell event detected")
            # Schedule reset for sticky value
            self._schedule_pulse_reset(DP_DOORBELL)

        # Hijack/duress: similar pulse handling
        hijack_val = new_status.get(DP_HIJACK)
        if hijack_val is True:
            old_val = old_status.get(DP_HIJACK)
            if old_val is not True:
                self._event_counts["hijack"] += 1
                self._fire_event("alarm_event", EVENT_TYPE_HIJACK)
                _LOGGER.warning("Hijack/duress event detected!")
            self._schedule_pulse_reset(DP_HIJACK)

        # Alarm: detect changes or same value with new timestamp
        alarm_val = new_status.get(DP_ALARM_LOCK)
        old_alarm = old_status.get(DP_ALARM_LOCK)
        if alarm_val and alarm_val != old_alarm:
            self._last_alarm_ts = now_ms
            self._event_counts["alarm"] += 1
            alarm_type = str(alarm_val).lower().replace(" ", "_")
            self._fire_event("alarm_event", alarm_type, {"alarm_type": alarm_val})
            _LOGGER.warning("Alarm event: %s", alarm_val)

        # Unlock DPs: detect any change
        for dp_code in ALL_UNLOCK_DPS:
            new_val = new_status.get(dp_code)
            old_val = old_status.get(dp_code)
            if new_val is not None and new_val != old_val:
                self._last_unlock_ts = now_ms
                self._event_counts["unlock"] += 1
                method = _extract_unlock_method(dp_code)
                self._fire_event(
                    "unlock_event",
                    method,
                    {"method": method, "value": new_val, "dp_code": dp_code},
                )
                _LOGGER.info("Unlock event: %s = %s", dp_code, new_val)

    @callback
    def _fire_event(
        self,
        entity_key: str,
        event_type: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Fire an event on the registered event entity."""
        entity = self._event_entities.get(entity_key)
        if entity:
            entity.fire_event(event_type, attributes)
        else:
            _LOGGER.debug(
                "Event entity %s not registered, skipping %s",
                entity_key,
                event_type,
            )

    async def _fetch_and_process_logs(self) -> None:
        """Fetch recent logs and fire events for new entries."""
        if self._last_event_timestamp_ms == 0:
            # First run: set to now - 1 minute to avoid flooding
            self._last_event_timestamp_ms = int(time.time() * 1000) - 60000

        try:
            unlock_events, alarm_events = await self.api.async_get_latest_events(
                self.device_id,
                since_timestamp=self._last_event_timestamp_ms,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch event logs: %s", err)
            return

        max_ts = self._last_event_timestamp_ms

        # Process unlock events from logs
        for event in unlock_events:
            ts = event.get("timestamp_ms", 0)
            if ts > max_ts:
                max_ts = ts

            # Extract unlock method from DPs or unlock_code
            method = "unknown"
            dps = event.get("dps") or []
            for dp in dps:
                if isinstance(dp, dict):
                    for key in dp:
                        if key.startswith("unlock_"):
                            method = _extract_unlock_method(key)
                            break
            if method == "unknown":
                code = event.get("unlock_code") or ""
                if code.startswith("unlock_"):
                    method = _extract_unlock_method(code)

            self._event_counts["unlock"] += 1
            self._fire_event(
                "unlock_event",
                method,
                {
                    "method": method,
                    "user_name": event.get("user_name"),
                    "unlock_name": event.get("unlock_name"),
                    "timestamp": ts,
                },
            )

        # Process alarm events from logs
        for event in alarm_events:
            ts = event.get("timestamp_ms", 0)
            if ts > max_ts:
                max_ts = ts

            alarm_type = event.get("alarm_type") or EVENT_TYPE_ALARM
            alarm_type = str(alarm_type).lower().replace(" ", "_")
            self._event_counts["alarm"] += 1
            self._fire_event(
                "alarm_event",
                alarm_type,
                {
                    "alarm_type": alarm_type,
                    "timestamp": ts,
                    "details": event.get("details"),
                },
            )

        if max_ts > self._last_event_timestamp_ms:
            self._last_event_timestamp_ms = max_ts

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            info = await self.api.async_get_device(self.device_id)
            status = await self.api.async_get_status(self.device_id)
        except Exception as err:  # noqa: BLE001 — surface as UpdateFailed
            if self.data:
                _LOGGER.warning("Cloud poll failed, keeping stale data: %s", err)
                return self.data
            raise UpdateFailed(str(err)) from err

        info = info or {}
        status = status or {}

        # Detect changes and fire events
        self._detect_status_changes(self._last_status_snapshot, status)

        # Apply any pulse resets (override sticky values)
        effective_status = dict(status)
        for dp_key, is_reset in list(self._last_status_snapshot.items()):
            if is_reset is False and dp_key in (DP_DOORBELL, DP_HIJACK):
                # Our reset override is still active
                if status.get(dp_key) is True:
                    effective_status[dp_key] = False

        # Update snapshot for next comparison
        self._last_status_snapshot = dict(status)

        # Fetch event logs (non-blocking, don't fail the update)
        try:
            await self._fetch_and_process_logs()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Event log fetch failed (non-fatal): %s", err)

        return {
            "device_id": self.device_id,
            "name": info.get("name") or DEVICE_NAME,
            "online": bool(info.get("online", True)),
            "product_name": info.get("product_name") or "",
            "category": info.get("category") or "videolock",
            "status": effective_status,
            # Extra data for sensors
            "event_counts": dict(self._event_counts),
            "last_doorbell_ts": self._last_doorbell_ts,
            "last_alarm_ts": self._last_alarm_ts,
            "last_unlock_ts": self._last_unlock_ts,
        }

    def get_effective_status(self, key: str, default: Any = None) -> Any:
        """Get status value with pulse reset applied."""
        if not self.data:
            return default
        return self.data.get("status", {}).get(key, default)
