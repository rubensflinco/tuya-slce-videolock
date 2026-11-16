"""Image platform — last doorbell snapshot."""

from __future__ import annotations

import logging

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .device import build_device_info
from .snapshots import DoorbellSnapshotGallery

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up last-doorbell image entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    gallery: DoorbellSnapshotGallery = data["snapshot_gallery"]
    device_id: str = data["device_id"]
    name = None
    coordinator = data.get("coordinator")
    if coordinator and coordinator.data:
        name = coordinator.data.get("name")
    async_add_entities(
        [SlceLastDoorbellImage(hass, gallery, device_id, name)]
    )


class SlceLastDoorbellImage(ImageEntity):
    """Still of the most recent doorbell ring."""

    _attr_has_entity_name = True
    _attr_name = "Última foto da campainha"
    _attr_content_type = "image/jpeg"
    _attr_icon = "mdi:doorbell-video"

    def __init__(
        self,
        hass: HomeAssistant,
        gallery: DoorbellSnapshotGallery,
        device_id: str,
        name: str | None,
    ) -> None:
        ImageEntity.__init__(self, hass)
        self._gallery = gallery
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_last_doorbell_image"
        self._attr_device_info = build_device_info(device_id, name)
        if gallery.latest_updated is not None:
            self._attr_image_last_updated = gallery.latest_updated

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._gallery.image_entity_id = self.entity_id
        self.async_on_remove(self._gallery.async_add_listener(self._on_new_snapshot))

    @callback
    def _on_new_snapshot(self) -> None:
        self._attr_image_last_updated = (
            self._gallery.latest_updated or dt_util.utcnow()
        )
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        return await self._gallery.async_get_latest_bytes()

    @property
    def extra_state_attributes(self) -> dict[str, int | str]:
        return {
            "retention_days": self._gallery.retention_days,
            "media_browser": "Mídia → Tuya SL-CE Videolock",
        }
