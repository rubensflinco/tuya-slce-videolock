"""Prefer Smart Life / Sharing stream (same path as official Tuya & Xtend).

Cloud OpenAPI ``stream/actions/allocate`` needs *IoT Video Live Stream*
authorized on the developer project. The official HA ``tuya`` integration
(and Xtend Sharing) already hold a consumer Smart Life session that can
allocate RTSP/HLS **without** that Cloud Service click — reuse it when the
same ``device_id`` is present.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Domains that expose a Sharing-style device_manager with allocate
_SHARING_DOMAINS: tuple[str, ...] = ("tuya", "xtend_tuya")


def _manager_from_entry(entry: Any) -> Any | None:
    """Best-effort extract Manager from official / Xtend config entry shapes."""
    runtime = getattr(entry, "runtime_data", None)
    if runtime is not None:
        for attr in ("manager", "device_manager", "multi_manager"):
            mgr = getattr(runtime, attr, None)
            if mgr is not None and hasattr(mgr, "get_device_stream_allocate"):
                return mgr
    return None


def _device_known(manager: Any, device_id: str) -> bool:
    device_map = getattr(manager, "device_map", None)
    if isinstance(device_map, dict):
        return device_id in device_map
    device_ids = getattr(manager, "device_ids", None)
    if isinstance(device_ids, (set, list, tuple, dict)):
        return device_id in device_ids
    # Unknown map — still try allocate
    return True


async def async_allocate_via_sharing(
    hass: HomeAssistant,
    device_id: str,
    stream_type: str = "rtsp",
) -> tuple[str | None, str | None]:
    """Return ``(url, source_label)`` using an already-loaded Tuya Sharing manager."""
    stype = (stream_type or "rtsp").strip().lower()

    for domain in _SHARING_DOMAINS:
        for entry in hass.config_entries.async_entries(domain):
            if entry.state != ConfigEntryState.LOADED:
                continue

            manager = _manager_from_entry(entry)
            if manager is None and domain == "tuya":
                # Current HA Core: entry.runtime_data is DeviceListener
                listener = entry.runtime_data
                manager = getattr(listener, "manager", None)

            if manager is None:
                # hass.data fallback (older / Xtend)
                bucket = hass.data.get(domain)
                if isinstance(bucket, dict):
                    slot = bucket.get(entry.entry_id)
                    if isinstance(slot, dict):
                        manager = (
                            slot.get("device_manager")
                            or slot.get("manager")
                            or slot.get("multi_manager")
                        )
                    else:
                        manager = getattr(slot, "manager", None) or getattr(
                            slot, "device_manager", None
                        )

            if manager is None or not hasattr(
                manager, "get_device_stream_allocate"
            ):
                continue
            if not _device_known(manager, device_id):
                continue

            try:
                url = await hass.async_add_executor_job(
                    manager.get_device_stream_allocate,
                    device_id,
                    stype,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "Sharing allocate via %s failed for %s (%s): %s",
                    domain,
                    device_id,
                    stype,
                    err,
                )
                continue

            if url:
                _LOGGER.info(
                    "Stream for %s via %s Sharing (%s)",
                    device_id,
                    domain,
                    stype,
                )
                return str(url), f"{domain}/sharing/{stype}"

    return None, None
