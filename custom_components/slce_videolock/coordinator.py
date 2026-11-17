"""Cloud-polling coordinator for SL-CE status DPs + event detection.

Enhanced coordinator that:
1. Polls status DPs every configured update_interval (default 60s)
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
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DEVICE_NAME,
    DOMAIN,
    DP_ALARM_LOCK,
    DP_DOORBELL,
    DP_HIJACK,
    EVENT_TYPE_ALARM,
    EVENT_TYPE_DOORBELL,
    EVENT_TYPE_HIJACK,
    PULSE_RESET_SECONDS,
    SNAPSHOT_KIND_ALARM,
    SNAPSHOT_KIND_DOORBELL,
    SNAPSHOT_KIND_UNLOCK,
)
from .tuya_api import TuyaCloudApi

if TYPE_CHECKING:
    from .event import SlceEventEntity
    from .snapshots import SnapshotGallery

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
        update_interval_seconds: int = DEFAULT_UPDATE_INTERVAL_SECONDS,
    ) -> None:
        self.api = api
        self.device_id = device_id
        self._event_entities: dict[str, "SlceEventEntity"] = {}
        self._snapshot_gallery: SnapshotGallery | None = None
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
        # Armados quando cloud está false; um disparo por "sessão" sticky true
        # (evita re-fire a cada poll enquanto doorbell=true no Tuya).
        self._doorbell_armed: bool = True
        self._hijack_armed: bool = True
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_seconds),
        )

    def register_event_entities(self, entities: list["SlceEventEntity"]) -> None:
        """Register event entities for dispatch."""
        for entity in entities:
            self._event_entities[entity.event_key] = entity

    def set_snapshot_gallery(self, gallery: SnapshotGallery) -> None:
        """Attach snapshot gallery (doorbell / unlock / alarm)."""
        self._snapshot_gallery = gallery

    @callback
    def _schedule_snapshot(
        self, kind: str, *, detail: str | None = None
    ) -> None:
        """Fire-and-forget still capture so poll cycle is not blocked."""
        gallery = self._snapshot_gallery
        if gallery is None:
            return
        self.hass.async_create_task(
            gallery.async_capture(kind, detail=detail)
        )

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
            # Mark as reset in snapshot + data so binary_sensor sees False
            self._last_status_snapshot[dp_key] = False
            if self.data and isinstance(self.data.get("status"), dict):
                new_data = dict(self.data)
                new_status = dict(new_data["status"])
                new_status[dp_key] = False
                new_data["status"] = new_status
                _LOGGER.debug("Pulse reset: %s → False", dp_key)
                self.async_set_updated_data(new_data)
            elif self.data:
                self.async_set_updated_data(self.data)

        self._pending_resets[dp_key] = async_call_later(
            self.hass, PULSE_RESET_SECONDS, _do_reset
        )

    def _detect_status_changes(
        self, old_status: dict[str, Any], new_status: dict[str, Any]
    ) -> None:
        """Detect changes in status DPs and fire events accordingly."""
        now_ms = int(time.time() * 1000)

        # Doorbell: cloud often leaves doorbell=true forever.
        # Fire ONCE when we first see true while armed; re-arm only on false.
        # First poll after start: disarm sticky true without firing (no spam on reload).
        doorbell_val = new_status.get(DP_DOORBELL)
        if doorbell_val is True:
            if not old_status:
                self._doorbell_armed = False
                self._schedule_pulse_reset(DP_DOORBELL)
            elif self._doorbell_armed:
                self._doorbell_armed = False
                self._last_doorbell_ts = now_ms
                self._event_counts["doorbell"] += 1
                self._fire_event("doorbell_event", EVENT_TYPE_DOORBELL)
                self._schedule_snapshot(SNAPSHOT_KIND_DOORBELL)
                _LOGGER.info("Doorbell event detected (rising edge)")
                self._schedule_pulse_reset(DP_DOORBELL)
        elif doorbell_val is False:
            self._doorbell_armed = True

        # Hijack/duress: same arming model (no re-fire while sticky true)
        hijack_val = new_status.get(DP_HIJACK)
        if hijack_val is True:
            if not old_status:
                self._hijack_armed = False
                self._schedule_pulse_reset(DP_HIJACK)
            elif self._hijack_armed:
                self._hijack_armed = False
                self._event_counts["hijack"] += 1
                self._fire_event("alarm_event", EVENT_TYPE_HIJACK)
                self._schedule_snapshot(
                    SNAPSHOT_KIND_ALARM, detail=EVENT_TYPE_HIJACK
                )
                _LOGGER.warning("Hijack/duress event detected!")
                self._schedule_pulse_reset(DP_HIJACK)
        elif hijack_val is False:
            self._hijack_armed = True

        # Alarm status DP is sticky (wrong_finger stays forever). Only fire on
        # real value change after baseline; repeats come from device logs.
        if old_status:
            alarm_val = new_status.get(DP_ALARM_LOCK)
            old_alarm = old_status.get(DP_ALARM_LOCK)
            if alarm_val and alarm_val != old_alarm:
                self._last_alarm_ts = now_ms
                self._event_counts["alarm"] += 1
                alarm_type = str(alarm_val).lower().replace(" ", "_")
                self._fire_event("alarm_event", alarm_type, {"alarm_type": alarm_val})
                self._schedule_snapshot(
                    SNAPSHOT_KIND_ALARM, detail=alarm_type
                )
                _LOGGER.warning("Alarm event (status change): %s", alarm_val)

        # Unlock DPs: only real changes after baseline (skip bootstrap).
        # Same face/fingerprint ID stays sticky — records API is the source of truth.
        if old_status:
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
                    self._schedule_snapshot(
                        SNAPSHOT_KIND_UNLOCK, detail=method
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
        """Fetch recent logs and fire events for new entries.

        Cloud status DPs for doorbell/unlock_face are sticky — door-lock/records
        is the reliable source (requires alphabetically sorted query for HMAC).
        """
        if not self._event_entities:
            # Platforms not ready yet — don't advance cursor past real events.
            return

        now_ms = int(time.time() * 1000)
        if self._last_event_timestamp_ms == 0:
            # Bootstrap: cursor = now so we don't replay hours of history.
            self._last_event_timestamp_ms = now_ms
            return

        try:
            unlock_events, alarm_events, doorbell_events = (
                await self.api.async_get_latest_events(
                    self.device_id,
                    since_timestamp=self._last_event_timestamp_ms,
                )
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch event logs: %s", err)
            return

        max_ts = self._last_event_timestamp_ms

        for event in doorbell_events:
            ts = int(event.get("timestamp_ms") or 0)
            if ts > max_ts:
                max_ts = ts
            self._last_doorbell_ts = ts or now_ms
            self._event_counts["doorbell"] += 1
            self._doorbell_armed = False
            self._fire_event("doorbell_event", EVENT_TYPE_DOORBELL, {
                "timestamp": ts,
                "record_id": event.get("record_id"),
            })
            self._schedule_snapshot(SNAPSHOT_KIND_DOORBELL)
            self._schedule_pulse_reset(DP_DOORBELL)
            _LOGGER.info("Doorbell event from records (ts=%s)", ts)

        for event in unlock_events:
            ts = int(event.get("timestamp_ms") or 0)
            if ts > max_ts:
                max_ts = ts

            method = "unknown"
            dps = event.get("dps") or []
            for dp in dps:
                if isinstance(dp, dict):
                    for key in dp:
                        if str(key).startswith("unlock_"):
                            method = _extract_unlock_method(str(key))
                            break
            if method == "unknown":
                code = event.get("unlock_code") or ""
                if str(code).startswith("unlock_"):
                    method = _extract_unlock_method(str(code))

            self._last_unlock_ts = ts or now_ms
            self._event_counts["unlock"] += 1
            self._fire_event(
                "unlock_event",
                method,
                {
                    "method": method,
                    "user_name": event.get("user_name"),
                    "unlock_name": event.get("unlock_name"),
                    "timestamp": ts,
                    "record_id": event.get("record_id"),
                },
            )
            self._schedule_snapshot(SNAPSHOT_KIND_UNLOCK, detail=method)
            _LOGGER.info("Unlock event from records: %s (ts=%s)", method, ts)

        for event in alarm_events:
            ts = int(event.get("timestamp_ms") or 0)
            if ts > max_ts:
                max_ts = ts

            alarm_type = event.get("alarm_type")
            if not alarm_type:
                for dp in event.get("dps") or []:
                    if isinstance(dp, dict) and DP_ALARM_LOCK in dp:
                        alarm_type = dp.get(DP_ALARM_LOCK)
                        break
            alarm_type = str(alarm_type or EVENT_TYPE_ALARM).lower().replace(" ", "_")
            self._last_alarm_ts = ts or now_ms
            self._event_counts["alarm"] += 1
            self._fire_event(
                "alarm_event",
                alarm_type,
                {
                    "alarm_type": alarm_type,
                    "timestamp": ts,
                    "details": event.get("details"),
                    "record_id": event.get("record_id"),
                },
            )
            self._schedule_snapshot(SNAPSHOT_KIND_ALARM, detail=alarm_type)
            _LOGGER.warning(
                "Alarm event from logs: %s (ts=%s source=%s)",
                alarm_type,
                ts,
                (event.get("details") or {}).get("source")
                if isinstance(event.get("details"), dict)
                else "records",
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

        # While disarmed (já tratamos o sticky true), binary fica off até cloud limpar
        effective_status = dict(status)
        if status.get(DP_DOORBELL) is True and not self._doorbell_armed:
            effective_status[DP_DOORBELL] = False
        if status.get(DP_HIJACK) is True and not self._hijack_armed:
            effective_status[DP_HIJACK] = False

        # Update snapshot for next comparison (cloud raw — arming controla o fire)
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
