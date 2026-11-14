"""Cloud-polling coordinator for SL-CE status DPs."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEVICE_NAME,
    DOMAIN,
    UPDATE_INTERVAL_SECONDS,
)
from .tuya_api import TuyaCloudApi

_LOGGER = logging.getLogger(__name__)


class SlceVideolockCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll device info + status from Tuya Cloud (~60 s)."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: TuyaCloudApi,
        device_id: str,
    ) -> None:
        self.api = api
        self.device_id = device_id
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            info = await self.api.async_get_device(self.device_id)
            status = await self.api.async_get_status(self.device_id)
        except Exception as err:  # noqa: BLE001 — surface as UpdateFailed
            if self.data:
                _LOGGER.warning("Cloud poll failed, keeping stale data: %s", err)
                return self.data
            raise UpdateFailed(str(err)) from err

        info = info or {}
        return {
            "device_id": self.device_id,
            "name": info.get("name") or DEVICE_NAME,
            "online": bool(info.get("online", True)),
            "product_name": info.get("product_name") or "",
            "category": info.get("category") or "videolock",
            "status": status,
        }
