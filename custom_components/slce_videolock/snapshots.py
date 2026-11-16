"""Doorbell snapshot gallery — capture, retain, purge, serve.

Photos are stored under ``<config>/slce_videolock/<device_id>/`` and exposed
via Media Browser (``media_source``) plus an ``image`` entity for the latest.
"""

from __future__ import annotations

import logging
import re
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
    SNAPSHOT_SUBDIR,
    clamp_retention_days,
)
from .stream_bridge import async_allocate_via_sharing
from .tuya_api import TuyaCloudApi

_LOGGER = logging.getLogger(__name__)

_FILENAME_RE = re.compile(
    r"^doorbell_(\d{8})_(\d{6})(?:_\d+)?\.jpg$",
    re.IGNORECASE,
)
_SAFE_DEVICE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_SAFE_FILE_RE = re.compile(
    r"^doorbell_\d{8}_\d{6}(?:_\d+)?\.jpg$",
    re.IGNORECASE,
)

# Re-export for callers that imported from this module
__all__ = [
    "DoorbellSnapshotGallery",
    "SnapshotMediaView",
    "clamp_retention_days",
    "device_snapshot_dir",
    "register_snapshot_http_views",
    "snapshot_root",
]


def snapshot_root(hass: HomeAssistant) -> Path:
    """Return ``<config>/slce_videolock``."""
    return Path(hass.config.path(SNAPSHOT_SUBDIR))


def device_snapshot_dir(hass: HomeAssistant, device_id: str) -> Path:
    """Return storage directory for one lock."""
    return snapshot_root(hass) / device_id


class DoorbellSnapshotGallery:
    """Capture and retain doorbell stills for one device."""

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
        self._listeners: list[Callable[[], None]] = []
        self._capture_lock = False
        self._latest_path: Path | None = None
        self._latest_updated: datetime | None = None
        # Set by image entity when available (links Activity entry to the photo)
        self.image_entity_id: str | None = None

    @property
    def storage_dir(self) -> Path:
        return device_snapshot_dir(self.hass, self.device_id)

    @property
    def media_source_uri(self) -> str:
        """URI opened from Media Browser for this lock's gallery."""
        return f"media-source://{DOMAIN}/{self.device_id}"

    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a callback when a new snapshot is saved."""
        self._listeners.append(listener)

        def _remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove

    def set_retention_days(self, days: int) -> None:
        """Update retention and schedule purge."""
        self.retention_days = clamp_retention_days(days)
        self.hass.async_create_task(self.async_purge_expired())

    @callback
    def _notify_listeners(self) -> None:
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Snapshot listener failed")

    async def async_setup(self) -> None:
        """Ensure directory exists, load latest, purge old files."""

        def _mkdir() -> None:
            self.storage_dir.mkdir(parents=True, exist_ok=True)

        await self.hass.async_add_executor_job(_mkdir)
        latest = await self.async_list_snapshots()
        if latest:
            self._latest_path = latest[0]
            self._latest_updated = _mtime_utc(latest[0])
        await self.async_purge_expired()

    async def async_list_snapshots(self) -> list[Path]:
        """Return snapshot paths newest-first."""

        def _list() -> list[Path]:
            folder = self.storage_dir
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

    async def async_get_latest_bytes(self) -> bytes | None:
        """Return bytes of the newest snapshot, if any."""
        path = self._latest_path
        if path is None:
            files = await self.async_list_snapshots()
            if not files:
                return None
            path = files[0]
            self._latest_path = path
            self._latest_updated = _mtime_utc(path)

        def _read() -> bytes | None:
            if not path.is_file():
                return None
            return path.read_bytes()

        return await self.hass.async_add_executor_job(_read)

    @property
    def latest_updated(self) -> datetime | None:
        return self._latest_updated

    async def async_capture_doorbell(self) -> Path | None:
        """Grab a still from the live stream and persist it."""
        if self._capture_lock:
            _LOGGER.debug("Doorbell snapshot already in progress for %s", self.device_id)
            return None
        self._capture_lock = True
        try:
            image = await self._async_grab_still()
            if not image:
                _LOGGER.warning(
                    "Doorbell snapshot failed for %s (no image from stream)",
                    self.device_id,
                )
                return None
            path = await self._async_write_snapshot(image)
            await self.async_purge_expired()
            self._latest_path = path
            self._latest_updated = dt_util.utcnow()
            self._notify_listeners()
            await self._async_log_activity(path)
            _LOGGER.info("Saved doorbell snapshot %s", path.name)
            return path
        finally:
            self._capture_lock = False

    async def _async_log_activity(self, path: Path) -> None:
        """Write an Activity (logbook) entry pointing to where the photo lives.

        The Activity panel does not render HTML/images, so the message uses
        plain text with the Media Browser path and media-source URI.
        """
        message = (
            f"Tirou uma foto da campainha ({path.name}). "
            "Para ver: Mídia → Tuya SL-CE Videolock "
            f"(ou abra a entidade «Última foto da campainha»). "
            f"Galeria: {self.media_source_uri}. "
            f"Retenção: {self.retention_days} dias."
        )
        data: dict[str, Any] = {
            "name": "Campainha — foto",
            "message": message,
            "domain": DOMAIN,
        }
        if self.image_entity_id:
            data["entity_id"] = self.image_entity_id
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
            _LOGGER.warning("ffmpeg unavailable for doorbell snapshot")
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
                "Could not allocate stream for doorbell snapshot (%s): %s",
                self.device_id,
                err or "unknown",
            )
        return url

    async def _async_write_snapshot(self, image: bytes) -> Path:
        now = dt_util.now()
        stamp = now.strftime("%Y%m%d_%H%M%S")

        def _write() -> Path:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            target = self.storage_dir / f"doorbell_{stamp}.jpg"
            suffix = 1
            while target.exists():
                target = self.storage_dir / f"doorbell_{stamp}_{suffix}.jpg"
                suffix += 1
            target.write_bytes(image)
            return target

        return await self.hass.async_add_executor_job(_write)

    async def async_purge_expired(self) -> int:
        """Delete snapshots older than retention; return count removed."""
        cutoff = dt_util.utcnow() - timedelta(days=self.retention_days)

        def _purge() -> int:
            folder = self.storage_dir
            if not folder.is_dir():
                return 0
            removed = 0
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
                "Purged %s doorbell snapshot(s) older than %sd for %s",
                removed,
                self.retention_days,
                self.device_id,
            )
            files = await self.async_list_snapshots()
            if files:
                self._latest_path = files[0]
                self._latest_updated = _mtime_utc(files[0])
            else:
                self._latest_path = None
                self._latest_updated = None
            self._notify_listeners()
        return removed


def _mtime_utc(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


class SnapshotMediaView(HomeAssistantView):
    """Serve retained doorbell JPEGs (auth required)."""

    url = SNAPSHOT_HTTP_URL_PREFIX + "/{device_id}/{filename}"
    name = "api:slce_videolock:snapshot"
    requires_auth = True

    async def get(self, request, device_id: str, filename: str):
        """Return a snapshot file if it belongs to a configured lock."""
        from aiohttp import web

        hass: HomeAssistant = request.app["hass"]
        if not _SAFE_DEVICE_RE.match(device_id):
            raise web.HTTPBadRequest()
        if not _SAFE_FILE_RE.match(filename) and not (
            filename.lower().startswith("doorbell_")
            and filename.lower().endswith(".jpg")
            and ".." not in filename
            and "/" not in filename
            and "\\" not in filename
        ):
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

        path = device_snapshot_dir(hass, device_id) / filename
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
