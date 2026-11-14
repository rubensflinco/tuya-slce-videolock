"""Camera platform — stub for SL-CE videolock stream.

Xtend Tuya proves the cloud delivers a camera for category ``videolock``, but
that project is GPL-3.0 — we must not copy its WebRTC/IPC implementation into
this MIT-licensed integration.

MVP status: entity is registered on the same device so Lovelace can show a
placeholder. Live RTSP/WebRTC will use OpenAPI stream allocate / webrtc-configs
(documented in docs/camera-todo.md) without importing xtend_tuya.
"""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SlceVideolockCoordinator
from .entity import SlceCoordinatorEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up camera stub entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: SlceVideolockCoordinator = data["coordinator"]
    device_id: str = data["device_id"]
    async_add_entities([SlceVideolockCamera(coordinator, device_id)])


class SlceVideolockCamera(SlceCoordinatorEntity, Camera):
    """Placeholder camera until OpenAPI stream path is implemented."""

    _attr_name = "Câmera"
    _attr_is_streaming = False

    def __init__(
        self,
        coordinator: SlceVideolockCoordinator,
        device_id: str,
    ) -> None:
        Camera.__init__(self)
        SlceCoordinatorEntity.__init__(self, coordinator, device_id, "camera")
        self._attr_unique_id = f"{device_id}_camera"

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """No snapshot yet — see docs/camera-todo.md."""
        _LOGGER.debug(
            "Camera snapshot not implemented for %s (stream TODO)",
            self._device_id,
        )
        return None

    async def stream_source(self) -> str | None:
        """Return None until RTSP/HLS allocate is wired."""
        return None
