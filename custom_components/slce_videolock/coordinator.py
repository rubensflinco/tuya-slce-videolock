"""DataUpdateCoordinator — cloud polling for SL-CE status DPs.

Cloud-only status path inspired by crestall/ha-tuya-lock-monitor (MIT).
LAN/tinytuya is intentionally out of scope (videolock local unlock is broken).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    META_REFRESH_SECONDS,
    UPDATE_INTERVAL,
)
from .tuya_api import TuyaApiError, TuyaCloudApi

_LOGGER = logging.getLogger(__name__)


class SlceVideolockCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll Tuya Cloud for device info + status DPs."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: TuyaCloudApi,
        device_id: str,
    ) -> None:
        self.api = api
        self.device_id = device_id
        self._cached_meta: dict[str, Any] = {}
        self._last_meta_refresh: float = 0.0
        self._last_contact: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    @property
    def last_contact(self) -> datetime | None:
        """UTC datetime of the last successful cloud poll."""
        return self._last_contact

    def _build_result(self, status: dict[str, Any]) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self._cached_meta.get("name") or DEFAULT_DEVICE_NAME,
            "online": bool(self._cached_meta.get("online", True)),
            "product_name": self._cached_meta.get("product_name") or "",
            "category": self._cached_meta.get("category") or "videolock",
            "status": status,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch device metadata (periodically) and status DPs."""
        now = time.time()
        need_meta = (
            not self._cached_meta
            or (now - self._last_meta_refresh) > META_REFRESH_SECONDS
        )

        try:
            if need_meta:
                self._cached_meta = await self.api.async_get_device_info(self.device_id)
                self._last_meta_refresh = now
            status = await self.api.async_get_status(self.device_id)
        except TuyaApiError as err:
            if self.data:
                _LOGGER.warning(
                    "Cloud poll failed for %s — returning stale data: %s",
                    self.device_id,
                    err,
                )
                return self.data
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001 — surface as UpdateFailed
            if self.data:
                _LOGGER.warning(
                    "Network error for %s — returning stale data: %s",
                    self.device_id,
                    err,
                )
                return self.data
            raise UpdateFailed(f"Network error: {err}") from err

        self._last_contact = dt_util.utcnow()
        return self._build_result(status)
