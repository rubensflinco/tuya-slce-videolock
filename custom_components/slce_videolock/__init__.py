"""SL-CE Videolock — unified unlock + camera + sensors for Tuya videolock."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_REGION,
    CONF_SNAPSHOT_RETENTION_DAYS,
    CONF_STREAM_TYPE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_DEVICE_NAME,
    DEFAULT_REGION,
    DEFAULT_SNAPSHOT_RETENTION_DAYS,
    DEFAULT_STREAM_TYPE,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
    MAX_UPDATE_INTERVAL_SECONDS,
    MIN_UPDATE_INTERVAL_SECONDS,
    clamp_retention_days,
)
from .coordinator import SlceVideolockCoordinator
from .snapshots import (
    SnapshotGallery,
    register_snapshot_http_views,
)
from .tuya_api import TuyaCloudApi

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LOCK,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.IMAGE,
]


def resolve_update_interval(entry: ConfigEntry) -> int:
    """Return clamped poll interval from options (preferred) or entry data."""
    raw = entry.options.get(
        CONF_UPDATE_INTERVAL,
        entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS),
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_UPDATE_INTERVAL_SECONDS
    return max(MIN_UPDATE_INTERVAL_SECONDS, min(MAX_UPDATE_INTERVAL_SECONDS, value))


def resolve_snapshot_retention_days(entry: ConfigEntry) -> int:
    """Return clamped doorbell snapshot retention from options or data."""
    raw = entry.options.get(
        CONF_SNAPSHOT_RETENTION_DAYS,
        entry.data.get(
            CONF_SNAPSHOT_RETENTION_DAYS, DEFAULT_SNAPSHOT_RETENTION_DAYS
        ),
    )
    return clamp_retention_days(raw)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SL-CE Videolock from a config entry."""
    session = async_get_clientsession(hass)
    api = TuyaCloudApi(
        access_id=entry.data[CONF_ACCESS_ID],
        access_secret=entry.data[CONF_ACCESS_SECRET],
        region=entry.data.get(CONF_REGION, DEFAULT_REGION),
        session=session,
    )
    device_id = entry.data[CONF_DEVICE_ID]
    device_name = entry.data.get(CONF_DEVICE_NAME) or DEFAULT_DEVICE_NAME
    update_interval = resolve_update_interval(entry)
    retention_days = resolve_snapshot_retention_days(entry)
    preferred_stream = entry.options.get(
        CONF_STREAM_TYPE,
        entry.data.get(CONF_STREAM_TYPE, DEFAULT_STREAM_TYPE),
    )
    coordinator = SlceVideolockCoordinator(
        hass, api, device_id, update_interval_seconds=update_interval
    )
    gallery = SnapshotGallery(
        hass,
        api=api,
        device_id=device_id,
        preferred_stream=str(preferred_stream or DEFAULT_STREAM_TYPE).lower(),
        retention_days=retention_days,
    )
    await gallery.async_setup()
    coordinator.set_snapshot_gallery(gallery)

    _LOGGER.debug(
        "SL-CE poll interval for %s: %ss; doorbell snapshot retention: %sd",
        device_id,
        update_interval,
        retention_days,
    )

    register_snapshot_http_views(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "device_id": device_id,
        "device_name": device_name,
        "snapshot_gallery": gallery,
    }

    # Platforms (incl. event entities) before first refresh so log→event works.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_config_entry_first_refresh()
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options (e.g. poll interval / retention) change."""
    await hass.config_entries.async_reload(entry.entry_id)
