"""Media Browser gallery — folders doorbell / unlock / alarm."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    SNAPSHOT_HTTP_URL_PREFIX,
    SNAPSHOT_KIND_LABELS,
    SNAPSHOT_KINDS,
)
from .snapshots import SnapshotGallery, kind_snapshot_dir

_LOGGER = logging.getLogger(__name__)

MIME_JPEG = "image/jpeg"


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up SL-CE snapshot media source."""
    return SlceSnapshotMediaSource(hass)


class SlceSnapshotMediaSource(MediaSource):
    """Browse retained photos by event kind."""

    name: str = "Tuya SL-CE Videolock"

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        device_id, kind, filename = _parse_identifier(item.identifier)
        if not device_id or not kind or not filename:
            raise Unresolvable(f"Incomplete media id: {item.identifier}")
        gallery = _gallery_for_device(self.hass, device_id)
        if gallery is None:
            raise Unresolvable(f"Unknown lock: {device_id}")
        path = kind_snapshot_dir(self.hass, device_id, kind) / filename
        exists = await self.hass.async_add_executor_job(path.is_file)
        if not exists:
            raise Unresolvable(f"Snapshot not found: {filename}")
        return PlayMedia(
            f"{SNAPSHOT_HTTP_URL_PREFIX}/{device_id}/{kind}/{filename}",
            MIME_JPEG,
            path=path,
        )

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        device_id, kind, filename = _parse_identifier(item.identifier)
        if filename:
            raise BrowseError(f"Cannot browse a file: {item.identifier}")

        if not device_id:
            return self._build_root()

        gallery = _gallery_for_device(self.hass, device_id)
        if gallery is None:
            raise BrowseError(f"Unknown lock: {device_id}")

        if not kind:
            return await self._build_device_folders(gallery)

        if kind not in SNAPSHOT_KINDS:
            raise BrowseError(f"Unknown folder: {kind}")
        return await self._build_kind_gallery(gallery, kind)

    def _build_root(self) -> BrowseMediaSource:
        children: list[BrowseMediaSource] = []
        domain_data = self.hass.data.get(DOMAIN) or {}
        for entry_id, entry_data in domain_data.items():
            if entry_id.startswith("_") or not isinstance(entry_data, dict):
                continue
            gallery = entry_data.get("snapshot_gallery")
            device_id = entry_data.get("device_id")
            if not isinstance(gallery, SnapshotGallery) or not device_id:
                continue
            title = entry_data.get("device_name") or device_id
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=device_id,
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.IMAGE,
                    title=str(title),
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.DIRECTORY,
                )
            )
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type="",
            title=self.name,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=children,
        )

    async def _build_device_folders(
        self, gallery: SnapshotGallery
    ) -> BrowseMediaSource:
        title = _device_title(self.hass, gallery.device_id) or gallery.device_id
        children: list[BrowseMediaSource] = []
        for kind in SNAPSHOT_KINDS:
            files = await gallery.async_list_snapshots(kind)
            label = SNAPSHOT_KIND_LABELS.get(kind, kind)
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{gallery.device_id}/{kind}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.IMAGE,
                    title=f"{label} ({len(files)})",
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.IMAGE,
                )
            )
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=gallery.device_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.IMAGE,
            title=str(title),
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=children,
        )

    async def _build_kind_gallery(
        self, gallery: SnapshotGallery, kind: str
    ) -> BrowseMediaSource:
        files = await gallery.async_list_snapshots(kind)
        label = SNAPSHOT_KIND_LABELS.get(kind, kind)
        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{gallery.device_id}/{kind}/{path.name}",
                media_class=MediaClass.IMAGE,
                media_content_type=MIME_JPEG,
                title=_pretty_title(path),
                thumbnail=(
                    f"{SNAPSHOT_HTTP_URL_PREFIX}/{gallery.device_id}/{kind}/{path.name}"
                ),
                can_play=True,
                can_expand=False,
            )
            for path in files
        ]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{gallery.device_id}/{kind}",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.IMAGE,
            title=f"{label} ({len(children)})",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.IMAGE,
            children=children,
        )


@callback
def _gallery_for_device(
    hass: HomeAssistant, device_id: str
) -> SnapshotGallery | None:
    domain_data = hass.data.get(DOMAIN) or {}
    for entry_id, entry_data in domain_data.items():
        if entry_id.startswith("_") or not isinstance(entry_data, dict):
            continue
        if entry_data.get("device_id") == device_id:
            gallery = entry_data.get("snapshot_gallery")
            if isinstance(gallery, SnapshotGallery):
                return gallery
    return None


@callback
def _device_title(hass: HomeAssistant, device_id: str) -> str | None:
    domain_data = hass.data.get(DOMAIN) or {}
    for entry_id, entry_data in domain_data.items():
        if entry_id.startswith("_") or not isinstance(entry_data, dict):
            continue
        if entry_data.get("device_id") == device_id:
            name = entry_data.get("device_name")
            return str(name) if name else None
    return None


def _parse_identifier(
    identifier: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Parse ``device``, ``device/kind`` or ``device/kind/file.jpg``."""
    if not identifier:
        return None, None, None
    parts = [p for p in identifier.strip("/").split("/") if p]
    device_id = parts[0] if parts else None
    kind = parts[1] if len(parts) > 1 else None
    filename = parts[2] if len(parts) > 2 else None
    return device_id, kind, filename


def _pretty_title(path: Path) -> str:
    name = path.stem
    parts = name.split("_")
    # unlock_YYYYMMDD_HHMMSS or YYYYMMDD_HHMMSS
    if len(parts) >= 3 and len(parts[1]) == 8 and len(parts[2]) >= 6:
        date_part, time_part = parts[1], parts[2]
    elif len(parts) >= 2 and len(parts[0]) == 8 and len(parts[1]) >= 6:
        date_part, time_part = parts[0], parts[1]
    else:
        return path.name
    return (
        f"{date_part[6:8]}/{date_part[4:6]}/{date_part[0:4]} "
        f"{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}"
    )
