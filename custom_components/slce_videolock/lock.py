"""Lock platform — Cloud ticket unlock/lock."""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_AUTO_LOCK_DELAY, DOMAIN
from .coordinator import SlceVideolockCoordinator
from .device import build_device_info
from .tuya_api import TuyaCloudApi

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lock entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    api: TuyaCloudApi = data["api"]
    coordinator: SlceVideolockCoordinator = data["coordinator"]
    device_id: str = data["device_id"]

    auto_lock = await api.async_get_auto_lock_time(device_id)
    if auto_lock is None:
        auto_lock = DEFAULT_AUTO_LOCK_DELAY

    async_add_entities(
        [SlceVideolockLock(coordinator, api, device_id, auto_lock)],
        True,
    )


class SlceVideolockLock(CoordinatorEntity[SlceVideolockCoordinator], LockEntity):
    """SL-CE door lock via Smart Lock password-ticket API."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: SlceVideolockCoordinator,
        api: TuyaCloudApi,
        device_id: str,
        auto_lock_time: int,
    ) -> None:
        super().__init__(coordinator)
        self._api = api
        self._device_id = device_id
        self._auto_lock_time = auto_lock_time
        self._attr_unique_id = f"{device_id}_lock"
        self._attr_is_locked = True
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        self._cancel_verify = None
        name = None
        if coordinator.data:
            name = coordinator.data.get("name")
        self._attr_device_info = build_device_info(device_id, name)

    async def async_update(self) -> None:
        """Refresh lock state from cloud."""
        try:
            state = await self._api.async_get_lock_state(self._device_id)
        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ConnectionError,
            KeyError,
            TypeError,
            ValueError,
        ) as err:
            _LOGGER.warning("Could not read lock state: %s", type(err).__name__)
            return
        if state is None:
            return
        self._attr_is_locked = not state
        self._attr_available = True

    async def async_unlock(self, **kwargs) -> None:
        self._attr_is_unlocking = True
        self.async_write_ha_state()
        success = await self._api.async_unlock(self._device_id)
        self._attr_is_unlocking = False
        if success:
            self._attr_is_locked = False
            self._attr_available = True
            self._schedule_verification(self._auto_lock_time + 1)
        self.async_write_ha_state()

    async def async_lock(self, **kwargs) -> None:
        self._attr_is_locking = True
        self.async_write_ha_state()
        success = await self._api.async_lock(self._device_id)
        self._attr_is_locking = False
        if success:
            self._attr_is_locked = True
            self._schedule_verification(5)
        self.async_write_ha_state()

    def _schedule_verification(self, delay: int) -> None:
        if self._cancel_verify is not None:
            self._cancel_verify()
            self._cancel_verify = None
        self._cancel_verify = async_call_later(
            self.hass, delay, self._async_verify_after_auto_lock
        )

    async def _async_verify_after_auto_lock(self, _now) -> None:
        self._cancel_verify = None
        await self.async_update()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._cancel_verify is not None:
            self._cancel_verify()
            self._cancel_verify = None
        await super().async_will_remove_from_hass()
