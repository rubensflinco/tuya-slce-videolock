"""Camera platform — OpenAPI allocate + fresh stream on each open."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.stream import Stream
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
    """Videolock camera via Cloud OpenAPI allocation.

    Tuya signed URLs expire within seconds if unused / minutes if used. HA's
    stream worker keeps the old URL → stuck spinner + ``Invalid data`` / 404.
    We discard the previous ``Stream`` on each open (same idea as Xtend).
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
                    "Ative o trial gratuito IoT Video Live Stream no projeto "
                    "Tuya Cloud (Cloud → Cloud Services)."
                )
        return attrs

    async def async_create_stream(self) -> Stream | None:
        """Always start a new HA Stream so ``stream_source`` reallocates."""
        old_stream = self.stream
        if old_stream is not None:
            await old_stream.stop()
            if self.stream is old_stream:
                self.stream = None
        return await super().async_create_stream()

    async def stream_source(self) -> str | None:
        """Return a freshly allocated live stream URL."""
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
        return url

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Grab a still via ffmpeg from a freshly allocated stream."""
        source = await self.stream_source()
        if not source:
            return None
        try:
            from homeassistant.components.ffmpeg import async_get_image
        except ImportError:
            _LOGGER.warning("ffmpeg component unavailable for snapshot")
            return None
        # RTSP from Tuya is often TCP-only behind their edge
        extra = None
        if source.lower().startswith("rtsp"):
            extra = "-rtsp_transport tcp"
        return await async_get_image(
            self.hass,
            source,
            extra_cmd=extra,
            width=width,
            height=height,
        )
