"""Sensors for Swiss Transit For HA."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import Departure
from .coordinator import TransitConfigEntry, TransitCoordinator
from .entity import TransitEntity

NEXT_DEPARTURES = 3


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors of one stop."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        DepartureSensor(coordinator, entry, index) for index in range(NEXT_DEPARTURES)
    ]
    entities += [
        DelaySensor(coordinator, entry),
        BoardSensor(coordinator, entry),
        AlertsSensor(coordinator, entry),
    ]
    async_add_entities(entities)


def _departure_attributes(dep: Departure) -> dict[str, Any]:
    trip: dict[str, Any] = {}
    if dep.arrival is not None:
        trip = {
            "arrival": (dep.arrival_time or dep.arrival).isoformat(),
            "arrival_delay": dep.arrival_delay,
            "duration": dep.duration,
            "transfers": dep.transfers,
            "route": " → ".join(leg.line for leg in dep.legs if leg.mode != "walk"),
        }
    return trip | {
        "line": dep.line,
        "mode": dep.mode,
        "destination": dep.destination,
        "platform": dep.platform,
        "platform_changed": dep.platform_changed,
        "planned": dep.planned.isoformat(),
        "delay": dep.delay,
        "cancelled": dep.cancelled,
        "realtime": dep.realtime,
        "operator": dep.operator,
    }


_MODE_ICONS = {
    "train": "mdi:train",
    "bus": "mdi:bus",
    "tram": "mdi:tram",
    "metro": "mdi:subway-variant",
    "ship": "mdi:ferry",
    "cableway": "mdi:gondola",
}


class DepartureSensor(TransitEntity, SensorEntity):
    """Time of the 1st, 2nd or 3rd next departure (real time when known)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: TransitCoordinator, entry: TransitConfigEntry, index: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, f"departure_{index + 1}")
        self._index = index
        self._attr_translation_key = f"departure_{index + 1}"

    @property
    def _departure(self) -> Departure | None:
        deps = self.coordinator.data.departures
        return deps[self._index] if len(deps) > self._index else None

    @property
    def native_value(self) -> datetime | None:
        """Departure time."""
        dep = self._departure
        return dep.time if dep else None

    @property
    def icon(self) -> str:
        """Icon of the vehicle."""
        dep = self._departure
        if dep and dep.cancelled:
            return "mdi:cancel"
        return _MODE_ICONS.get(dep.mode if dep else "", "mdi:bus-clock")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Line, destination, platform and delay."""
        dep = self._departure
        return _departure_attributes(dep) if dep else None


class DelaySensor(TransitEntity, SensorEntity):
    """Delay of the next departure."""

    _attr_translation_key = "delay"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TransitCoordinator, entry: TransitConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "delay")

    @property
    def native_value(self) -> int | None:
        """Delay in minutes, None without real-time data."""
        deps = self.coordinator.data.departures
        return deps[0].delay if deps else None


class BoardSensor(TransitEntity, SensorEntity):
    """The whole departure board, for the card and templates."""

    _attr_translation_key = "departures"
    _attr_icon = "mdi:timetable"
    _attr_native_unit_of_measurement = "departures"
    _unrecorded_attributes = frozenset({"departures", "alerts"})

    def __init__(self, coordinator: TransitCoordinator, entry: TransitConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "departures")

    @property
    def native_value(self) -> int:
        """Number of departures shown."""
        return len(self.coordinator.data.departures)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Departures and alerts as lists."""
        data = self.coordinator.data
        return {
            "stop_id": data.stop_id,
            "stop_name": data.stop_name,
            "source": data.source,
            "walk_time": self.coordinator.walk_time,
            "trip": data.trip,
            "to_name": data.to_name,
            "departures": [d.as_dict() for d in data.departures],
            "alerts": [s.as_dict() for s in data.situations],
            "swisstransit_board": True,
        }


class AlertsSensor(TransitEntity, SensorEntity):
    """Number of active disruption messages."""

    _attr_translation_key = "alerts"
    _attr_icon = "mdi:alert-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"alerts"})

    def __init__(self, coordinator: TransitCoordinator, entry: TransitConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "alerts")

    @property
    def native_value(self) -> int:
        """Number of messages."""
        return len(self.coordinator.data.situations)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The messages."""
        return {"alerts": [s.as_dict() for s in self.coordinator.data.situations]}
