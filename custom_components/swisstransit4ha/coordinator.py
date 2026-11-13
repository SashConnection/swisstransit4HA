"""Data update coordinator for Swiss Transit For HA."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    Board,
    Departure,
    OjpClient,
    OpenTransportClient,
    Situation,
    TransitAuthError,
    TransitError,
)
from .const import (
    CONF_API_KEY,
    CONF_DELAY_THRESHOLD,
    CONF_DESTINATION,
    CONF_KIND,
    CONF_LIMIT,
    CONF_LINES,
    CONF_MODES,
    CONF_SCAN_INTERVAL,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    CONF_TO_ID,
    CONF_TO_NAME,
    CONF_WALK_TIME,
    DEFAULT_DELAY_THRESHOLD,
    DEFAULT_LIMIT,
    DEFAULT_SCAN_INTERVAL_OJP,
    DEFAULT_SCAN_INTERVAL_OPEN,
    DEFAULT_WALK_TIME,
    DOMAIN,
    FETCH_MARGIN,
    KIND_TRIP,
    MAX_FETCH,
    MODES,
)

_LOGGER = logging.getLogger(__name__)

type TransitConfigEntry = ConfigEntry[TransitCoordinator]


@dataclass(slots=True)
class TransitData:
    """What the entities show."""

    stop_id: str
    stop_name: str
    source: str
    departures: list[Departure]
    situations: list[Situation]
    delay_threshold: int
    to_name: str | None = None

    @property
    def trip(self) -> bool:
        """Trips from one stop to another instead of a departure board."""
        return self.to_name is not None

    @property
    def disrupted(self) -> bool:
        """Any active message, cancellation or delay over the threshold."""
        return bool(self.situations) or any(
            d.cancelled or (d.delay or 0) >= self.delay_threshold for d in self.departures
        )


def split_lines(value: str | None) -> set[str]:
    """Lines typed as "1, 9, S3" -> {"1", "9", "S3"} (upper case)."""
    if not value:
        return set()
    return {p.strip().replace(" ", "").upper() for p in value.replace(";", ",").split(",") if p.strip()}


def filter_departures(
    departures: list[Departure],
    *,
    modes: list[str] | None,
    lines: set[str],
    destination: str | None,
    walk_time: int,
    limit: int,
) -> list[Departure]:
    """Keep the departures the user can and wants to take."""
    earliest = dt_util.utcnow() + timedelta(minutes=walk_time)
    wanted_dest = (destination or "").strip().lower()
    all_modes = not modes or set(modes) >= set(MODES)
    kept: list[Departure] = []
    for dep in departures:
        if dep.time < earliest:
            continue
        if not all_modes and dep.mode not in modes:
            continue
        if lines and dep.line.upper() not in lines:
            continue
        if wanted_dest and wanted_dest not in dep.destination.lower():
            continue
        kept.append(dep)
    return kept[:limit]


class TransitCoordinator(DataUpdateCoordinator[TransitData]):
    """Fetch the departure board of one stop."""

    config_entry: TransitConfigEntry

    def __init__(self, hass: HomeAssistant, entry: TransitConfigEntry) -> None:
        """Initialize the coordinator."""
        options = {**entry.data, **entry.options}
        api_key = (options.get(CONF_API_KEY) or "").strip()
        session = async_get_clientsession(hass)
        self.client: OjpClient | OpenTransportClient = (
            OjpClient(session, api_key) if api_key else OpenTransportClient(session)
        )
        default_interval = DEFAULT_SCAN_INTERVAL_OJP if api_key else DEFAULT_SCAN_INTERVAL_OPEN
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.data[CONF_STOP_NAME]}",
            update_interval=timedelta(
                seconds=int(options.get(CONF_SCAN_INTERVAL) or default_interval)
            ),
        )
        self.stop_id: str = entry.data[CONF_STOP_ID]
        self.stop_name: str = entry.data[CONF_STOP_NAME]
        self.trip = entry.data.get(CONF_KIND) == KIND_TRIP
        self.to_id: str | None = entry.data.get(CONF_TO_ID)
        self.to_name: str | None = entry.data.get(CONF_TO_NAME)
        self._limit = int(options.get(CONF_LIMIT, DEFAULT_LIMIT))
        # Line, direction and vehicle filters only apply to a departure board.
        self._modes: list[str] | None = None if self.trip else options.get(CONF_MODES) or None
        self._lines = set() if self.trip else split_lines(options.get(CONF_LINES))
        self._destination: str | None = (
            None if self.trip else options.get(CONF_DESTINATION) or None
        )
        self.walk_time = int(options.get(CONF_WALK_TIME, DEFAULT_WALK_TIME))
        self._delay_threshold = int(options.get(CONF_DELAY_THRESHOLD, DEFAULT_DELAY_THRESHOLD))

    @property
    def _fetch_count(self) -> int:
        if self.trip:
            return min(16, self._limit + 3)
        filtered = bool(self._lines or self._destination or self._modes)
        count = self._limit * (FETCH_MARGIN if filtered else 1) + 3
        return min(MAX_FETCH, count)

    async def _async_update_data(self) -> TransitData:
        language = (self.hass.config.language or "en")[:2]
        try:
            if self.trip and self.to_id:
                board: Board = await self.client.trip(
                    self.stop_id, self.to_id, self._fetch_count, language
                )
            else:
                board = await self.client.board(self.stop_id, self._fetch_count, language)
        except TransitAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TransitError as err:
            raise UpdateFailed(str(err)) from err

        departures = filter_departures(
            board.departures,
            modes=self._modes,
            lines=self._lines,
            destination=self._destination,
            walk_time=self.walk_time,
            limit=self._limit,
        )
        now = dt_util.utcnow()
        shown_ids = {sid for d in departures for sid in d.situations}
        situations = [
            s
            for s in board.situations
            if (s.start is None or s.start <= now)
            and (s.end is None or s.end >= now)
            # Messages tied to departures the user filtered away are noise.
            and (s.id in shown_ids or not _linked(board, s.id))
        ]
        return TransitData(
            stop_id=self.stop_id,
            stop_name=f"{self.stop_name} → {self.to_name}" if self.trip else self.stop_name,
            source=board.source,
            departures=departures,
            situations=situations,
            delay_threshold=self._delay_threshold,
            to_name=self.to_name if self.trip else None,
        )


def _linked(board: Board, situation_id: str) -> bool:
    """Whether a message is attached to some departure of the board."""
    return any(situation_id in d.situations for d in board.departures)
