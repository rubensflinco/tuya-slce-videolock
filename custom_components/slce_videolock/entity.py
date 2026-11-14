"""Shared entity helpers — one device_registry device per lock."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_DEVICE_NAME, DOMAIN, MANUFACTURER, MODEL
from .coordinator import SlceVideolockCoordinator


def build_device_info(
    device_id: str,
    *,
    name: str | None = None,
    model: str | None = None,
) -> DeviceInfo:
    """Return DeviceInfo with identifiers (slce_videolock, device_id)."""
    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=name or DEFAULT_DEVICE_NAME,
        manufacturer=MANUFACTURER,
        model=model or MODEL,
    )


class SlceCoordinatorEntity(CoordinatorEntity[SlceVideolockCoordinator]):
    """Base entity linked to the shared coordinator + device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SlceVideolockCoordinator,
        device_id: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{unique_suffix}"
        name = None
        model = None
        if coordinator.data:
            name = coordinator.data.get("name")
            product = coordinator.data.get("product_name")
            if product:
                model = product
        self._attr_device_info = build_device_info(
            device_id, name=name, model=model
        )
