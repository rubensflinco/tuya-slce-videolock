"""Camera platform — live stream via Tuya OpenAPI allocate (Xtend IoT path).

Uses the same Cloud endpoint documented by Tuya / used by Xtend's IoT manager:
``POST /v1.0/devices/{device_id}/stream/actions/allocate`` with type rtsp|hls|…

Implementation is original MIT code (no GPL copy from xtend_tuya).
Requires **IoT Video Live Stream** free trial on iot.tuya.com (same as Xtend docs).
"""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SlceVideolockCoordinator
from .entity import SlceCoordinatorEntity
from .tuya_api import TuyaCloudApi

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SL-CE camera entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: SlceVideolockCoordinator = data["coordinator"]
    device_id: str = data["device_id"]
    api: TuyaCloudApi = data["api"]
    async_add_entities([SlceVideolockCamera(coordinator, device_id, api)])


class SlceVideolockCamera(SlceCoordinatorEntity, Camera):
    """Videolock camera using Cloud stream allocate (RTSP/HLS)."""

    _attr_name = "Câmera"
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        coordinator: SlceVideolockCoordinator,
        device_id: str,
        api: TuyaCloudApi,
    ) -> None:
        Camera.__init__(self)
        SlceCoordinatorEntity.__init__(self, coordinator, device_id, "camera")
        self._api = api
        self._attr_unique_id = f"{device_id}_camera"
        self._attr_is_streaming = False

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """HA will pull a frame via ffmpeg from stream_source when available."""
        return None

    async def stream_source(self) -> str | None:
        """Return RTSP/HLS URL from Tuya stream allocate."""
        url = await self._api.async_get_stream_url(self._device_id)
        if url:
            self._attr_is_streaming = True
            _LOGGER.debug("Camera stream source ready for %s", self._device_id)
        else:
            self._attr_is_streaming = False
            _LOGGER.warning(
                "Sem URL de stream para %s — ative IoT Video Live Stream no "
                "projeto iot.tuya.com (mesmo passo do Xtend Tuya)",
                self._device_id,
            )
        return url
