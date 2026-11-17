"""Event snapshot gallery — capture, retain, purge, serve.

Layout::

    <config>/slce_videolock/<device_id>/
      doorbell/   # campainha
      unlock/     # acesso liberado
      alarm/      # alarme de segurança

Exposed via Media Browser + per-kind ``image`` entities.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    SNAPSHOT_HTTP_URL_PREFIX,
    SNAPSHOT_KIND_ALARM,
    SNAPSHOT_KIND_DOORBELL,
    SNAPSHOT_KIND_LABELS,
    SNAPSHOT_KIND_UNLOCK,
    SNAPSHOT_KINDS,
    SNAPSHOT_SUBDIR,
    clamp_retention_days,
)
from .stream_bridge import async_allocate_via_sharing
from .tuya_api import TuyaCloudApi

_LOGGER = logging.getLogger(__name__)

_FILENAME_RE = re.compile(
    r"^(?:doorbell_|unlock_|alarm_)?(\d{8})_(\d{6})(?:_\d+)?\.jpg$",
    re.IGNORECASE,
)
_SAFE_DEVICE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_SAFE_KIND_RE = re.compile(r"^(doorbell|unlock|alarm)$")
_SAFE_FILE_RE = re.compile(
    r"^(?:doorbell_|unlock_|alarm_)?\d{8}_\d{6}(?:_\d+)?\.jpg$",
    re.IGNORECASE,
)

__all__ = [
    "DoorbellSnapshotGallery",
    "SnapshotGallery",
    "SnapshotMediaView",
    "clamp_retention_days",
    "device_snapshot_dir",
    "kind_snapshot_dir",
    "register_snapshot_http_views",
    "snapshot_root",
]


def snapshot_root(hass: HomeAssistant) -> Path:
    """Return ``<config>/slce_videolock``."""
    return Path(hass.config.path(SNAPSHOT_SUBDIR))


def device_snapshot_dir(hass: HomeAssistant, device_id: str) -> Path:
    """Return storage directory for one lock."""
    return snapshot_root(hass) / device_id


def kind_snapshot_dir(hass: HomeAssistant, device_id: str, kind: str) -> Path:
    """Return ``…/<device_id>/<kind>/``."""
    return device_snapshot_dir(hass, device_id) / kind


class SnapshotGallery:
    """Capture and retain stills for doorbell, unlock and alarm events."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        api: TuyaCloudApi,
        device_id: str,
        preferred_stream: str,
        retention_days: int,
    ) -> None:
        self.hass = hass
        self.api = api
        self.device_id = device_id
        self.preferred_stream = preferred_stream
        self.retention_days = clamp_retention_days(retention_days)
        self._listeners: dict[str, list[Callable[[], None]]] = {
            kind: [] for kind in SNAPSHOT_KINDS
        }
        self._capture_lock = asyncio.Lock()
        self._latest_path: dict[str, Path | None] = {kind: None for kind in SNAPSHOT_KINDS}
        self._latest_updated: dict[str, datetime | None] = {
            kind: None for kind in SNAPSHOT_KINDS
        }
        # Set by image entities (links Activity entry to the photo)
        self.image_entity_ids: dict[str, str | None] = {
            kind: None for kind in SNAPSHOT_KINDS
        }

    # Backward-compatible alias used by older call sites
    @property
    def image_entity_id(self) -> str | None:
        return self.image_entity_ids.get(SNAPSHOT_KIND_DOORBELL)

    @image_entity_id.setter
    def image_entity_id(self, value: str | None) -> None:
        self.image_entity_ids[SNAPSHOT_KIND_DOORBELL] = value

    @property
    def storage_dir(self) -> Path:
        return device_snapshot_dir(self.hass, self.device_id)

    def kind_dir(self, kind: str) -> Path:
        return kind_snapshot_dir(self.hass, self.device_id, kind)

    def media_source_uri(self, kind: str | None = None) -> str:
        """URI for Media Browser (device or kind folder)."""
        if kind:
            return f"media-source://{DOMAIN}/{self.device_id}/{kind}"
        return f"media-source://{DOMAIN}/{self.device_id}"

    def async_add_listener(
        self, kind: str, listener: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a callback when a new snapshot of ``kind`` is saved."""
        if kind not in self._listeners:
            self._listeners[kind] = []
        self._listeners[kind].append(listener)

        def _remove() -> None:
            if listener in self._listeners.get(kind, []):
                self._listeners[kind].remove(listener)

        return _remove

    def set_retention_days(self, days: int) -> None:
        """Update retention and schedule purge."""
        self.retention_days = clamp_retention_days(days)
        self.hass.async_create_task(self.async_purge_expired())

    def latest_updated(self, kind: str) -> datetime | None:
        return self._latest_updated.get(kind)

    @callback
    def _notify_listeners(self, kind: str) -> None:
        for listener in list(self._listeners.get(kind, [])):
            try:
                listener()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Snapshot listener failed (%s)", kind)

    async def async_setup(self) -> None:
        """Ensure directories exist, migrate legacy flat files, purge."""

        def _prepare() -> None:
            root = self.storage_dir
            root.mkdir(parents=True, exist_ok=True)
            for kind in SNAPSHOT_KINDS:
                (root / kind).mkdir(parents=True, exist_ok=True)
            # Migrate 0.7.x flat doorbell_*.jpg into doorbell/
            doorbell_dir = root / SNAPSHOT_KIND_DOORBELL
            for path in list(root.iterdir()):
                if not path.is_file():
                    continue
                name = path.name
                if not name.lower().endswith(".jpg"):
                    continue
                lower = name.lower()
                if lower.startswith("doorbell_"):
                    target = doorbell_dir / name
                elif lower.startswith("unlock_"):
                    target = root / SNAPSHOT_KIND_UNLOCK / name
                elif lower.startswith("alarm_"):
                    target = root / SNAPSHOT_KIND_ALARM / name
                else:
                    continue
                if not target.exists():
                    try:
                        shutil.move(str(path), str(target))
                    except OSError as err:
                        _LOGGER.debug("Migrate snapshot failed %s: %s", path, err)

        await self.hass.async_add_executor_job(_prepare)
        for kind in SNAPSHOT_KINDS:
            files = await self.async_list_snapshots(kind)
            if files:
                self._latest_path[kind] = files[0]
                self._latest_updated[kind] = _mtime_utc(files[0])
        await self.async_purge_expired()

    async def async_list_snapshots(self, kind: str) -> list[Path]:
        """Return snapshot paths for ``kind``, newest-first."""

        def _list() -> list[Path]:
            folder = self.kind_dir(kind)
            if not folder.is_dir():
                return []
            files = [
                path
                for path in folder.iterdir()
                if path.is_file() and _FILENAME_RE.match(path.name)
            ]
            files.sort(key=lambda p: p.name, reverse=True)
            return files

        return await self.hass.async_add_executor_job(_list)

    async def async_get_latest_bytes(self, kind: str) -> bytes | None:
        """Return bytes of the newest snapshot for ``kind``."""
        path = self._latest_path.get(kind)
        if path is None:
            files = await self.async_list_snapshots(kind)
            if not files:
                return None
            path = files[0]
            self._latest_path[kind] = path
            self._latest_updated[kind] = _mtime_utc(path)

        def _read() -> bytes | None:
            if not path.is_file():
                return None
            return path.read_bytes()

        return await self.hass.async_add_executor_job(_read)

    async def async_capture_doorbell(self) -> Path | None:
        """Compatibility wrapper for doorbell captures."""
        return await self.async_capture(SNAPSHOT_KIND_DOORBELL)

    async def async_capture(
        self,
        kind: str,
        *,
        detail: str | None = None,
    ) -> Path | None:
        """Grab a still from the live stream and persist it under ``kind``."""
        if kind not in SNAPSHOT_KINDS:
            _LOGGER.warning("Unknown snapshot kind %s", kind)
            return None
        async with self._capture_lock:
            image = await self._async_grab_still()
            if not image:
                _LOGGER.warning(
                    "Snapshot (%s) failed for %s (no image from stream)",
                    kind,
                    self.device_id,
                )
                return None
            path = await self._async_write_snapshot(kind, image)
            await self.async_purge_expired()
            self._latest_path[kind] = path
            self._latest_updated[kind] = dt_util.utcnow()
            self._notify_listeners(kind)
            await self._async_log_activity(kind, path, detail=detail)
            _LOGGER.info("Saved %s snapshot %s", kind, path.name)
            return path

    async def _async_log_activity(
        self,
        kind: str,
        path: Path,
        *,
        detail: str | None = None,
    ) -> None:
        """Write an Activity entry pointing to where the photo lives."""
        label = SNAPSHOT_KIND_LABELS.get(kind, kind)
        detail_bit = f" ({detail})" if detail else ""
        message = (
            f"Tirou uma foto — {label}{detail_bit} ({path.name}). "
            f"Para ver: Mídia → Tuya SL-CE Videolock → {label} "
            f"(ou entidade «Última foto — {label}»). "
            f"Galeria: {self.media_source_uri(kind)}. "
            f"Retenção: {self.retention_days} dias."
        )
        data: dict[str, Any] = {
            "name": f"{label} — foto",
            "message": message,
            "domain": DOMAIN,
        }
        entity_id = self.image_entity_ids.get(kind)
        if entity_id:
            data["entity_id"] = entity_id
        try:
            await self.hass.services.async_call(
                "logbook",
                "log",
                data,
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Could not write Activity entry for snapshot: %s", err)

    async def _async_grab_still(self) -> bytes | None:
        """Allocate stream and extract one JPEG via ffmpeg."""
        source = await self._async_stream_url()
        if not source:
            return None
        try:
            from homeassistant.components.ffmpeg import async_get_image
        except ImportError:
            _LOGGER.warning("ffmpeg unavailable for snapshot")
            return None
        extra = None
        if source.lower().startswith("rtsp"):
            extra = "-rtsp_transport tcp"
        return await async_get_image(
            self.hass,
            source,
            extra_cmd=extra,
        )

    async def _async_stream_url(self) -> str | None:
        for stype in ("rtsp", "hls"):
            url, _label = await async_allocate_via_sharing(
                self.hass, self.device_id, stype
            )
            if url:
                return url
        url, _used, err = await self.api.async_allocate_stream_preferred(
            self.device_id, self.preferred_stream
        )
        if not url:
            _LOGGER.warning(
                "Could not allocate stream for snapshot (%s): %s",
                self.device_id,
                err or "unknown",
            )
        return url

    async def _async_write_snapshot(self, kind: str, image: bytes) -> Path:
        now = dt_util.now()
        stamp = now.strftime("%Y%m%d_%H%M%S")
        folder = self.kind_dir(kind)

        def _write() -> Path:
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{kind}_{stamp}.jpg"
            suffix = 1
            while target.exists():
                target = folder / f"{kind}_{stamp}_{suffix}.jpg"
                suffix += 1
            target.write_bytes(image)
            return target

        return await self.hass.async_add_executor_job(_write)

    async def async_purge_expired(self) -> int:
        """Delete snapshots older than retention across all kinds."""
        cutoff = dt_util.utcnow() - timedelta(days=self.retention_days)

        def _purge() -> int:
            removed = 0
            for kind in SNAPSHOT_KINDS:
                folder = self.kind_dir(kind)
                if not folder.is_dir():
                    continue
                for path in folder.iterdir():
                    if not path.is_file() or not _FILENAME_RE.match(path.name):
                        continue
                    try:
                        mtime = datetime.fromtimestamp(
                            path.stat().st_mtime, tz=timezone.utc
                        )
                    except OSError:
                        continue
                    if mtime < cutoff:
                        try:
                            path.unlink()
                            removed += 1
                        except OSError as err:
                            _LOGGER.debug("Failed to delete %s: %s", path, err)
            return removed

        removed = await self.hass.async_add_executor_job(_purge)
        if removed:
            _LOGGER.info(
                "Purged %s snapshot(s) older than %sd for %s",
                removed,
                self.retention_days,
                self.device_id,
            )
            for kind in SNAPSHOT_KINDS:
                files = await self.async_list_snapshots(kind)
                if files:
                    self._latest_path[kind] = files[0]
                    self._latest_updated[kind] = _mtime_utc(files[0])
                else:
                    self._latest_path[kind] = None
                    self._latest_updated[kind] = None
                self._notify_listeners(kind)
        return removed


# Alias kept for imports from 0.7.x
DoorbellSnapshotGallery = SnapshotGallery


def _mtime_utc(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


class SnapshotMediaView(HomeAssistantView):
    """Serve retained event JPEGs (auth required)."""

    url = SNAPSHOT_HTTP_URL_PREFIX + "/{device_id}/{kind}/{filename}"
    name = "api:slce_videolock:snapshot"
    requires_auth = True

    async def get(self, request, device_id: str, kind: str, filename: str):
        """Return a snapshot file if it belongs to a configured lock."""
        from aiohttp import web

        hass: HomeAssistant = request.app["hass"]
        if not _SAFE_DEVICE_RE.match(device_id):
            raise web.HTTPBadRequest()
        if not _SAFE_KIND_RE.match(kind):
            raise web.HTTPBadRequest()
        if not _SAFE_FILE_RE.match(filename):
            raise web.HTTPBadRequest()

        domain_data = hass.data.get(DOMAIN) or {}
        known = False
        for entry_data in domain_data.values():
            if not isinstance(entry_data, dict):
                continue
            if entry_data.get("device_id") == device_id:
                known = True
                break
        if not known:
            raise web.HTTPNotFound()

        path = kind_snapshot_dir(hass, device_id, kind) / filename
        exists = await hass.async_add_executor_job(path.is_file)
        if not exists:
            raise web.HTTPNotFound()
        return web.FileResponse(path)


def register_snapshot_http_views(hass: HomeAssistant) -> None:
    """Register the snapshot HTTP view once."""
    domain = hass.data.setdefault(DOMAIN, {})
    if domain.get("_snapshot_view_registered"):
        return
    hass.http.register_view(SnapshotMediaView)
    domain["_snapshot_view_registered"] = True
