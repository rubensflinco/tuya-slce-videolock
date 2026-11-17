"""Image platform — last snapshot per event kind (doorbell / unlock / alarm)."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    SNAPSHOT_KIND_ALARM,
    SNAPSHOT_KIND_DOORBELL,
    SNAPSHOT_KIND_LABELS,
    SNAPSHOT_KIND_UNLOCK,
)
from .device import build_device_info
from .snapshots import SnapshotGallery

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _ImageDesc:
    kind: str
    name: str
    icon: str
    unique_suffix: str


_IMAGE_DESCS: tuple[_ImageDesc, ...] = (
    _ImageDesc(
        kind=SNAPSHOT_KIND_DOORBELL,
        name="Última foto — Campainha",
        icon="mdi:doorbell-video",
        unique_suffix="last_doorbell_image",
    ),
    _ImageDesc(
        kind=SNAPSHOT_KIND_UNLOCK,
        name="Última foto — Acesso liberado",
        icon="mdi:lock-open-variant",
        unique_suffix="last_unlock_image",
    ),
    _ImageDesc(
        kind=SNAPSHOT_KIND_ALARM,
        name="Última foto — Alarme",
        icon="mdi:alarm-light",
        unique_suffix="last_alarm_image",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up last-snapshot image entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    gallery: SnapshotGallery = data["snapshot_gallery"]
    device_id: str = data["device_id"]
    name = None
    coordinator = data.get("coordinator")
    if coordinator and coordinator.data:
        name = coordinator.data.get("name")
    async_add_entities(
        [
            SlceLastEventImage(hass, gallery, device_id, name, desc)
            for desc in _IMAGE_DESCS
        ]
    )


class SlceLastEventImage(ImageEntity):
    """Still of the most recent event of one kind."""

    _attr_has_entity_name = True
    _attr_content_type = "image/jpeg"

    def __init__(
        self,
        hass: HomeAssistant,
        gallery: SnapshotGallery,
        device_id: str,
        name: str | None,
        desc: _ImageDesc,
    ) -> None:
        ImageEntity.__init__(self, hass)
        self._gallery = gallery
        self._kind = desc.kind
        self._device_id = device_id
        self._attr_name = desc.name
        self._attr_icon = desc.icon
        self._attr_unique_id = f"{device_id}_{desc.unique_suffix}"
        self._attr_device_info = build_device_info(device_id, name)
        updated = gallery.latest_updated(desc.kind)
        if updated is not None:
            self._attr_image_last_updated = updated

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._gallery.image_entity_ids[self._kind] = self.entity_id
        self.async_on_remove(
            self._gallery.async_add_listener(self._kind, self._on_new_snapshot)
        )

    @callback
    def _on_new_snapshot(self) -> None:
        self._attr_image_last_updated = (
            self._gallery.latest_updated(self._kind) or dt_util.utcnow()
        )
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        return await self._gallery.async_get_latest_bytes(self._kind)

    @property
    def extra_state_attributes(self) -> dict[str, int | str]:
        label = SNAPSHOT_KIND_LABELS.get(self._kind, self._kind)
        return {
            "snapshot_kind": self._kind,
            "retention_days": self._gallery.retention_days,
            "media_browser": f"Mídia → Tuya SL-CE Videolock → {label}",
        }
