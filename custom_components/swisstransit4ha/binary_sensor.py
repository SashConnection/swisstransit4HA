"""Binary sensor for Swiss Transit For HA."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TransitConfigEntry, TransitCoordinator
from .entity import TransitEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the disruption sensor of one stop."""
    async_add_entities([DisruptionSensor(entry.runtime_data, entry)])


class DisruptionSensor(TransitEntity, BinarySensorEntity):
    """On when a message is active, a departure is cancelled or late."""

    _attr_translation_key = "disruption"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: TransitCoordinator, entry: TransitConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "disruption")

    @property
    def is_on(self) -> bool:
        """Whether something goes wrong at this stop."""
        return self.coordinator.data.disrupted

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Why."""
        data = self.coordinator.data
        return {
            "alerts": [s.summary for s in data.situations],
            "cancelled": [f"{d.line} → {d.destination}" for d in data.departures if d.cancelled],
            "delayed": [
                f"{d.line} → {d.destination} +{d.delay}'"
                for d in data.departures
                if (d.delay or 0) >= data.delay_threshold
            ],
        }
