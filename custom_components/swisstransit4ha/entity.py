"""Base entity for Swiss Transit For HA."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import TransitConfigEntry, TransitCoordinator


class TransitEntity(CoordinatorEntity[TransitCoordinator]):
    """Common attributes: one device per configured stop."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: TransitCoordinator, entry: TransitConfigEntry, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=f"Trip {coordinator.stop_id} → {coordinator.to_id}"
            if coordinator.trip
            else f"Stop {coordinator.stop_id}",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://opentransportdata.swiss/",
        )
