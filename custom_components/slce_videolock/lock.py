"""Lock platform — Cloud ticket unlock/lock (Smart Lock Open Service).

Command flow adapted from nicolasglg/tuya-smart-lock (MIT):
password-ticket → password-free door-operate.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import DEFAULT_AUTO_LOCK_DELAY, DOMAIN
from .coordinator import SlceVideolockCoordinator
from .entity import SlceCoordinatorEntity
from .tuya_api import TuyaCloudApi, infer_is_locked

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

    auto_lock_time = DEFAULT_AUTO_LOCK_DELAY
    try:
        fetched = await api.async_get_auto_lock_time(device_id)
        if fetched is not None:
            auto_lock_time = fetched
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("auto_lock_time unavailable: %s", err)

    async_add_entities(
        [SlceVideolockLock(coordinator, api, device_id, auto_lock_time)]
    )


class SlceVideolockLock(SlceCoordinatorEntity, LockEntity):
    """SL-CE door lock controlled via Tuya Smart Lock ticket API."""

    _attr_name = None  # device name is the lock name
    _attr_translation_key = "lock"

    def __init__(
        self,
        coordinator: SlceVideolockCoordinator,
        api: TuyaCloudApi,
        device_id: str,
        auto_lock_time: int,
    ) -> None:
        super().__init__(coordinator, device_id, "lock")
        self._api = api
        self._auto_lock_time = auto_lock_time
        self._attr_is_locked = True
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        self._cancel_verify = None
        self._apply_status_from_coordinator()

    def _apply_status_from_coordinator(self) -> None:
        if not self.coordinator.data:
            return
        status = self.coordinator.data.get("status") or {}
        inferred = infer_is_locked(status)
        if inferred is not None:
            self._attr_is_locked = inferred

    def _handle_coordinator_update(self) -> None:
        self._apply_status_from_coordinator()
        super()._handle_coordinator_update()

    async def async_unlock(self, **kwargs) -> None:
        """Unlock via Cloud ticket API."""
        self._attr_is_unlocking = True
        self.async_write_ha_state()

        success = await self._api.async_unlock(self._device_id)

        self._attr_is_unlocking = False
        if success:
            self._attr_is_locked = False
            self._attr_available = True
        self.async_write_ha_state()

        if success:
            self._schedule_verification(self._auto_lock_time + 1)

    async def async_lock(self, **kwargs) -> None:
        """Lock via Cloud ticket API."""
        self._attr_is_locking = True
        self.async_write_ha_state()

        success = await self._api.async_lock(self._device_id)

        self._attr_is_locking = False
        if success:
            # Command accepted ≠ bolt moved; verify after a short delay
            self._attr_available = False
            self._schedule_verification(5)
        self.async_write_ha_state()

    def _schedule_verification(self, delay: int) -> None:
        self._cancel_pending_verification()
        self._cancel_verify = async_call_later(
            self.hass, delay, self._async_verify_after_auto_lock
        )

    def _cancel_pending_verification(self) -> None:
        if self._cancel_verify is not None:
            self._cancel_verify()
            self._cancel_verify = None

    async def async_will_remove_from_hass(self) -> None:
        self._cancel_pending_verification()
        await super().async_will_remove_from_hass()

    async def _async_verify_after_auto_lock(self, _now) -> None:
        self._cancel_verify = None
        was_available = self._attr_available
        previous = self._attr_is_locked
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
            _LOGGER.warning(
                "Could not verify lock state for %s: %s",
                self._device_id,
                type(err).__name__,
            )
            return

        if state is None:
            return

        # API returns True if unlocked
        self._attr_is_locked = not state
        self._attr_available = True
        if self._attr_available == was_available and self._attr_is_locked == previous:
            return
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
