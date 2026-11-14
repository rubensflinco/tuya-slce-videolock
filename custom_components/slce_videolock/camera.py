"""Camera platform — Tuya Cloud stream allocate (HLS/RTSP) + ffmpeg snapshot."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STREAM_TYPE, DEFAULT_STREAM_TYPE, DOMAIN
from .coordinator import SlceVideolockCoordinator
from .device import build_device_info
from .tuya_api import TuyaCloudApi

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up camera entity on the same device as lock/sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    api: TuyaCloudApi = data["api"]
    coordinator: SlceVideolockCoordinator = data["coordinator"]
    device_id: str = data["device_id"]
    preferred = entry.options.get(
        CONF_STREAM_TYPE,
        entry.data.get(CONF_STREAM_TYPE, DEFAULT_STREAM_TYPE),
    )
    async_add_entities([SlceVideolockCamera(coordinator, api, device_id, preferred)])


class SlceVideolockCamera(CoordinatorEntity[SlceVideolockCoordinator], Camera):
    """Videolock camera via Cloud stream allocate.

    On each stream start / snapshot, allocates a fresh signed URL from Tuya
    (URLs expire). Prefer HLS for Home Assistant ffmpeg; fall back to RTSP.

    HA Core exposes ``Camera`` (not ``CameraEntity``) on current releases.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        coordinator: SlceVideolockCoordinator,
        api: TuyaCloudApi,
        device_id: str,
        preferred_stream: str,
    ) -> None:
        super().__init__(coordinator)
        Camera.__init__(self)
        self._api = api
        self._device_id = device_id
        self._preferred_stream = (preferred_stream or DEFAULT_STREAM_TYPE).lower()
        self._attr_unique_id = f"{device_id}_camera"
        self._last_stream_type: str | None = None
        self._last_stream_error: str | None = None
        name = None
        if coordinator.data:
            name = coordinator.data.get("name")
        self._attr_device_info = build_device_info(device_id, name)

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        if not self.coordinator.data:
            return True
        return bool(self.coordinator.data.get("online", True))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "preferred_stream": self._preferred_stream,
        }
        if self._last_stream_type:
            attrs["allocated_stream_type"] = self._last_stream_type
        if self._last_stream_error:
            attrs["stream_error"] = self._last_stream_error
            if "not subscribed" in self._last_stream_error.lower():
                attrs["stream_fix_hint"] = (
                    "Ative o trial IoT Video Live Stream no projeto Tuya Cloud "
                    "(Cloud → Cloud Services / Service API), como no Xtend Tuya."
                )
        return attrs

    async def stream_source(self) -> str | None:
        """Return a freshly allocated live stream URL for HA stream/ffmpeg."""
        url, used, err = await self._api.async_allocate_stream_preferred(
            self._device_id, self._preferred_stream
        )
        self._last_stream_type = used
        self._last_stream_error = err
        if not url:
            _LOGGER.error(
                "Could not allocate stream for %s (preferred=%s): %s",
                self._device_id,
                self._preferred_stream,
                err or "unknown",
            )
            return None
        _LOGGER.debug("Allocated %s stream for %s", used, self._device_id)
        return url

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Grab a still via ffmpeg from the allocated stream."""
        source = await self.stream_source()
        if not source:
            return None
        try:
            from homeassistant.components.ffmpeg import async_get_image
        except ImportError:
            _LOGGER.warning("ffmpeg component unavailable for snapshot")
            return None
        return await async_get_image(
            self.hass,
            source,
            extra_cmd=None,
            width=width,
            height=height,
        )
