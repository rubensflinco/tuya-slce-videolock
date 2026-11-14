"""Shared DeviceInfo helper — one HA device for lock + sensors + camera."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DEVICE_NAME, DOMAIN, MANUFACTURER, MODEL


def build_device_info(device_id: str, name: str | None = None) -> DeviceInfo:
    """Return DeviceInfo keyed by (slce_videolock, device_id)."""
    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=name or DEVICE_NAME,
        manufacturer=MANUFACTURER,
        model=MODEL,
    )
