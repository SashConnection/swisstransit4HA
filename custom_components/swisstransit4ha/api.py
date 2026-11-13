"""Clients for Swiss public transport open data.

Two sources, same result shape:

* transport.opendata.ch: free, no key. Timetable for every stop, real-time
  delays mostly for trains.
* opentransportdata.swiss OJP 2.0: free key. Real-time for most operators
  (buses and trams included), cancellations, and disruption messages (SIRI-SX
  situations) linked to each departure.

This module has no Home Assistant import so it can be tested on its own.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import aiohttp

_LOGGER = logging.getLogger(__name__)

OPEN_URL = "https://transport.opendata.ch/v1"
OJP_URL = "https://api.opentransportdata.swiss/ojp20"
TIMEOUT = aiohttp.ClientTimeout(total=20)
USER_AGENT = "swisstransit4ha (Home Assistant integration)"

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


class TransitError(Exception):
    """The source could not be reached or answered with an error."""


class TransitAuthError(TransitError):
    """The API key was refused."""


@dataclass(slots=True)
class Stop:
    """A stop or station that can be chosen."""

    id: str
    name: str
    mode: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(slots=True)
class Situation:
    """A disruption message."""

    id: str
    summary: str
    description: str | None = None
    severity: str | None = None
    start: datetime | None = None
    end: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON friendly copy."""
        return {
            "id": self.id,
            "summary": self.summary,
            "description": self.description,
            "severity": self.severity,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
        }


@dataclass(slots=True)
class Leg:
    """One vehicle of a trip."""

    line: str
    mode: str
    destination: str
    board: str
    alight: str
    departure: datetime | None = None
    arrival: datetime | None = None
    platform: str | None = None
    cancelled: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON friendly copy."""
        return {
            "line": self.line,
            "mode": self.mode,
            "destination": self.destination,
            "from": self.board,
            "to": self.alight,
            "departure": self.departure.isoformat() if self.departure else None,
            "arrival": self.arrival.isoformat() if self.arrival else None,
            "platform": self.platform,
            "cancelled": self.cancelled,
        }


@dataclass(slots=True)
class Departure:
    """One departure from the chosen stop."""

    line: str
    mode: str
    destination: str
    planned: datetime
    expected: datetime | None = None
    category: str | None = None
    operator: str | None = None
    platform: str | None = None
    planned_platform: str | None = None
    cancelled: bool = False
    realtime: bool = False
    situations: list[str] = field(default_factory=list)
    # Trip mode only: arrival at the destination stop and the vehicles taken.
    arrival: datetime | None = None
    arrival_expected: datetime | None = None
    transfers: int | None = None
    legs: list[Leg] = field(default_factory=list)

    @property
    def time(self) -> datetime:
        """Best known departure time."""
        return self.expected or self.planned

    @property
    def delay(self) -> int | None:
        """Delay in whole minutes, None without real-time data."""
        if self.expected is None:
            return None
        return max(0, round((self.expected - self.planned).total_seconds() / 60))

    @property
    def platform_changed(self) -> bool:
        """Whether the departure leaves from another platform than planned."""
        return bool(
            self.platform and self.planned_platform and self.platform != self.planned_platform
        )

    @property
    def arrival_time(self) -> datetime | None:
        """Best known arrival time (trip mode)."""
        return self.arrival_expected or self.arrival

    @property
    def arrival_delay(self) -> int | None:
        """Arrival delay in whole minutes (trip mode)."""
        if self.arrival is None or self.arrival_expected is None:
            return None
        return max(0, round((self.arrival_expected - self.arrival).total_seconds() / 60))

    @property
    def duration(self) -> int | None:
        """Travel time in minutes (trip mode)."""
        if self.arrival is None:
            return None
        if self.arrival_expected is not None:
            return round((self.arrival_expected - self.time).total_seconds() / 60)
        return round((self.arrival - self.planned).total_seconds() / 60)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON friendly copy, used by the card."""
        trip: dict[str, Any] = {}
        if self.arrival is not None:
            trip = {
                "arrival": self.arrival.isoformat(),
                "arrival_expected": self.arrival_expected.isoformat()
                if self.arrival_expected
                else None,
                "arrival_delay": self.arrival_delay,
                "duration": self.duration,
                "transfers": self.transfers,
                "legs": [leg.as_dict() for leg in self.legs],
            }
        return trip | {
            "line": self.line,
            "mode": self.mode,
            "category": self.category,
            "destination": self.destination,
            "operator": self.operator,
            "planned": self.planned.isoformat(),
            "expected": self.expected.isoformat() if self.expected else None,
            "delay": self.delay,
            "platform": self.platform,
            "platform_changed": self.platform_changed,
            "cancelled": self.cancelled,
            "realtime": self.realtime,
            "situations": self.situations,
        }


@dataclass(slots=True)
class Board:
    """Departures and disruptions for one stop."""

    stop_id: str
    stop_name: str
    source: str
    departures: list[Departure]
    situations: list[Situation] = field(default_factory=list)


# --- transport.opendata.ch -------------------------------------------------

_OPEN_TRAIN = {
    "IC", "ICE", "ICN", "IR", "IRE", "RE", "R", "S", "SN", "EC", "EN", "TGV", "RJ",
    "RJX", "NJ", "PE", "EXT", "CNL", "TER", "D", "RB", "ARZ", "TE2", "IN", "EXT",
}
_OPEN_BUS = {"B", "BN", "BUS", "NFB", "KB", "EXB", "BP", "TX", "RUB", "EV", "BAR"}
_OPEN_TRAM = {"T", "NFT", "TN"}
_OPEN_METRO = {"M"}
_OPEN_SHIP = {"BAT", "BAV", "FAE", "KAT"}
_OPEN_CABLE = {"FUN", "PB", "GB", "SL", "LB", "ASC", "CC", "SB"}
_OPEN_ICONS = {
    "train": "train",
    "bus": "bus",
    "tram": "tram",
    "ship": "ship",
    "cableway": "cableway",
    "funicular": "cableway",
}


def open_mode(category: str | None) -> str:
    """Map a transport.opendata.ch category to a mode."""
    cat = (category or "").upper()
    for mode, cats in (
        ("train", _OPEN_TRAIN),
        ("bus", _OPEN_BUS),
        ("tram", _OPEN_TRAM),
        ("metro", _OPEN_METRO),
        ("ship", _OPEN_SHIP),
        ("cableway", _OPEN_CABLE),
    ):
        if cat in cats:
            return mode
    return "other"


def line_label(mode: str, category: str | None, number: str | None) -> str:
    """Line as shown on the boards: IC1, S3, R8, 9, m2."""
    category = (category or "").strip()
    number = (number or "").strip()
    if not number:
        return category
    if mode == "train" and category and not number.upper().startswith(category.upper()):
        # Long-distance trains sometimes carry the train number, not a line.
        if number.isdigit() and len(number) > 3:
            return category
        return f"{category}{number}"
    return number


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        _LOGGER.debug("Unreadable time %s", value)
        return None


class OpenTransportClient:
    """transport.opendata.ch, no key."""

    source = "transport.opendata.ch"

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self._session = session

    async def _get(self, path: str, params: list[tuple[str, str]]) -> dict[str, Any]:
        try:
            async with self._session.get(
                f"{OPEN_URL}/{path}",
                params=params,
                timeout=TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            ) as resp:
                if resp.status == 429:
                    raise TransitError("transport.opendata.ch rate limit reached")
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise TransitError(f"transport.opendata.ch: {err}") from err

    async def search(self, query: str) -> list[Stop]:
        """Find stops and stations by name."""
        data = await self._get("locations", [("query", query), ("type", "station")])
        stops: list[Stop] = []
        for item in data.get("stations") or []:
            if not item.get("id") or not item.get("name"):
                continue
            coord = item.get("coordinate") or {}
            stops.append(
                Stop(
                    id=str(item["id"]),
                    name=item["name"],
                    mode=_OPEN_ICONS.get(item.get("icon") or ""),
                    latitude=coord.get("x"),
                    longitude=coord.get("y"),
                )
            )
        return stops

    async def board(self, stop_id: str, limit: int, language: str = "en") -> Board:
        """Next departures from a stop."""
        fields = [
            "station/id",
            "station/name",
            "stationboard/stop/departure",
            "stationboard/stop/delay",
            "stationboard/stop/platform",
            "stationboard/stop/prognosis/departure",
            "stationboard/stop/prognosis/platform",
            "stationboard/category",
            "stationboard/number",
            "stationboard/to",
            "stationboard/operator",
        ]
        params = [("id", stop_id), ("limit", str(limit))]
        params += [("fields[]", f) for f in fields]
        data = await self._get("stationboard", params)
        station = data.get("station") or {}
        departures: list[Departure] = []
        for item in data.get("stationboard") or []:
            stop = item.get("stop") or {}
            planned = _parse_time(stop.get("departure"))
            if planned is None:
                continue
            prognosis = stop.get("prognosis") or {}
            expected = _parse_time(prognosis.get("departure"))
            delay = stop.get("delay")
            if expected is None and isinstance(delay, int):
                expected = planned + timedelta(minutes=delay)
            mode = open_mode(item.get("category"))
            planned_platform = stop.get("platform") or None
            departures.append(
                Departure(
                    line=line_label(mode, item.get("category"), item.get("number")),
                    mode=mode,
                    category=item.get("category"),
                    destination=item.get("to") or "",
                    operator=item.get("operator"),
                    planned=planned,
                    expected=expected,
                    platform=prognosis.get("platform") or planned_platform,
                    planned_platform=planned_platform,
                    realtime=expected is not None,
                )
            )
        return Board(
            stop_id=str(station.get("id") or stop_id),
            stop_name=station.get("name") or stop_id,
            source=self.source,
            departures=departures,
        )


    async def trip(self, from_id: str, to_id: str, limit: int, language: str = "en") -> Board:
        """Next connections from one stop to another, transfers included."""
        fields = [
            "connections/from",
            "connections/to/station/name",
            "connections/to/arrival",
            "connections/to/delay",
            "connections/to/platform",
            "connections/to/prognosis/arrival",
            "connections/transfers",
            "connections/sections/walk",
            "connections/sections/journey/category",
            "connections/sections/journey/number",
            "connections/sections/journey/to",
            "connections/sections/journey/operator",
            "connections/sections/departure/station/name",
            "connections/sections/departure/departure",
            "connections/sections/departure/platform",
            "connections/sections/departure/prognosis/departure",
            "connections/sections/arrival/station/name",
            "connections/sections/arrival/arrival",
            "connections/sections/arrival/prognosis/arrival",
        ]
        params = [("from", from_id), ("to", to_id), ("limit", str(min(16, max(1, limit))))]
        params += [("fields[]", f) for f in fields]
        data = await self._get("connections", params)
        departures: list[Departure] = []
        from_name = to_name = None
        for conn in data.get("connections") or []:
            start = conn.get("from") or {}
            end = conn.get("to") or {}
            planned = _parse_time(start.get("departure"))
            arrival = _parse_time(end.get("arrival"))
            if planned is None or arrival is None:
                continue
            from_name = from_name or (start.get("station") or {}).get("name")
            to_name = to_name or (end.get("station") or {}).get("name")
            expected = _parse_time((start.get("prognosis") or {}).get("departure"))
            if expected is None and isinstance(start.get("delay"), int):
                expected = planned + timedelta(minutes=start["delay"])
            arrival_expected = _parse_time((end.get("prognosis") or {}).get("arrival"))
            if arrival_expected is None and isinstance(end.get("delay"), int):
                arrival_expected = arrival + timedelta(minutes=end["delay"])

            legs: list[Leg] = []
            for section in conn.get("sections") or []:
                journey = section.get("journey")
                dep = section.get("departure") or {}
                arr = section.get("arrival") or {}
                if not journey:
                    if section.get("walk") is not None:
                        legs.append(
                            Leg(
                                line="",
                                mode="walk",
                                destination="",
                                board=(dep.get("station") or {}).get("name") or "",
                                alight=(arr.get("station") or {}).get("name") or "",
                                departure=_parse_time(dep.get("departure")),
                                arrival=_parse_time(arr.get("arrival")),
                            )
                        )
                    continue
                mode = open_mode(journey.get("category"))
                legs.append(
                    Leg(
                        line=line_label(mode, journey.get("category"), journey.get("number")),
                        mode=mode,
                        destination=journey.get("to") or "",
                        board=(dep.get("station") or {}).get("name") or "",
                        alight=(arr.get("station") or {}).get("name") or "",
                        departure=_parse_time((dep.get("prognosis") or {}).get("departure"))
                        or _parse_time(dep.get("departure")),
                        arrival=_parse_time((arr.get("prognosis") or {}).get("arrival"))
                        or _parse_time(arr.get("arrival")),
                        platform=dep.get("platform") or None,
                    )
                )
            first = next((leg for leg in legs if leg.mode != "walk"), None)
            prognosis_platform = (start.get("prognosis") or {}).get("platform")
            planned_platform = start.get("platform") or None
            departures.append(
                Departure(
                    line=first.line if first else "",
                    mode=first.mode if first else "other",
                    destination=first.destination if first else (to_name or ""),
                    planned=planned,
                    expected=expected,
                    platform=prognosis_platform or planned_platform,
                    planned_platform=planned_platform,
                    realtime=expected is not None,
                    arrival=arrival,
                    arrival_expected=arrival_expected,
                    transfers=conn.get("transfers"),
                    legs=legs,
                )
            )
        departures.sort(key=lambda d: d.time)
        return Board(
            stop_id=from_id,
            stop_name=f"{from_name or from_id} → {to_name or to_id}",
            source=self.source,
            departures=departures,
        )


# --- opentransportdata.swiss OJP 2.0 --------------------------------------

_OJP_MODES = {
    "rail": "train",
    "suburbanrail": "train",
    "urbanrail": "train",
    "intercityrail": "train",
    "bus": "bus",
    "coach": "bus",
    "trolleybus": "bus",
    "tram": "tram",
    "metro": "metro",
    "underground": "metro",
    "water": "ship",
    "ferry": "ship",
    "telecabin": "cableway",
    "funicular": "cableway",
    "cableway": "cableway",
    "lift": "cableway",
}

_STOP_EVENT_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<OJP xmlns="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="2.0">
  <OJPRequest>
    <siri:ServiceRequest>
      <siri:ServiceRequestContext>
        <siri:Language>{lang}</siri:Language>
      </siri:ServiceRequestContext>
      <siri:RequestTimestamp>{now}</siri:RequestTimestamp>
      <siri:RequestorRef>swisstransit4ha</siri:RequestorRef>
      <OJPStopEventRequest>
        <siri:RequestTimestamp>{now}</siri:RequestTimestamp>
        <siri:MessageIdentifier>{msg}</siri:MessageIdentifier>
        <Location>
          <PlaceRef>
            <StopPlaceRef>{stop}</StopPlaceRef>
          </PlaceRef>
          <DepArrTime>{now}</DepArrTime>
        </Location>
        <Params>
          <NumberOfResults>{limit}</NumberOfResults>
          <StopEventType>departure</StopEventType>
          <IncludePreviousCalls>false</IncludePreviousCalls>
          <IncludeOnwardCalls>false</IncludeOnwardCalls>
          <UseRealtimeData>full</UseRealtimeData>
        </Params>
      </OJPStopEventRequest>
    </siri:ServiceRequest>
  </OJPRequest>
</OJP>"""


_TRIP_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<OJP xmlns="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="2.0">
  <OJPRequest>
    <siri:ServiceRequest>
      <siri:ServiceRequestContext>
        <siri:Language>{lang}</siri:Language>
      </siri:ServiceRequestContext>
      <siri:RequestTimestamp>{now}</siri:RequestTimestamp>
      <siri:RequestorRef>swisstransit4ha</siri:RequestorRef>
      <OJPTripRequest>
        <siri:RequestTimestamp>{now}</siri:RequestTimestamp>
        <siri:MessageIdentifier>{msg}</siri:MessageIdentifier>
        <Origin>
          <PlaceRef>
            <StopPlaceRef>{origin}</StopPlaceRef>
          </PlaceRef>
          <DepArrTime>{now}</DepArrTime>
        </Origin>
        <Destination>
          <PlaceRef>
            <StopPlaceRef>{destination}</StopPlaceRef>
          </PlaceRef>
        </Destination>
        <Params>
          <NumberOfResults>{limit}</NumberOfResults>
          <IncludeIntermediateStops>false</IncludeIntermediateStops>
          <UseRealtimeData>full</UseRealtimeData>
        </Params>
      </OJPTripRequest>
    </siri:ServiceRequest>
  </OJPRequest>
</OJP>"""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(elem: ET.Element | None, *names: str) -> ET.Element | None:
    """Follow a path of local names, ignoring namespaces."""
    for name in names:
        if elem is None:
            return None
        elem = next((c for c in elem if _local(c.tag) == name), None)
    return elem


def _children(elem: ET.Element | None, name: str) -> list[ET.Element]:
    if elem is None:
        return []
    return [c for c in elem if _local(c.tag) == name]


def _descendants(elem: ET.Element, name: str) -> list[ET.Element]:
    return [e for e in elem.iter() if _local(e.tag) == name]


def _text(elem: ET.Element | None, *names: str) -> str | None:
    found = _child(elem, *names)
    if found is None or found.text is None:
        return None
    return found.text.strip() or None


def _lang_text(elems: list[ET.Element], language: str) -> str | None:
    """Pick the text in the wanted language, then English, German, any."""
    texts: dict[str, str] = {}
    for elem in elems:
        value = "".join(elem.itertext()).strip()
        if value:
            texts.setdefault((elem.get(XML_LANG) or "").lower()[:2], value)
    for lang in (language, "en", "de", "fr", "it", ""):
        if lang in texts:
            return texts[lang]
    return next(iter(texts.values()), None)


def _parse_situation(elem: ET.Element, language: str) -> Situation | None:
    number = _text(elem, "SituationNumber")
    if not number:
        return None
    summary = _lang_text(_descendants(elem, "SummaryText"), language) or _lang_text(
        _descendants(elem, "Summary"), language
    )
    description = _lang_text(_descendants(elem, "DescriptionText"), language) or _lang_text(
        _descendants(elem, "Description"), language
    )
    if not summary and not description:
        return None
    validity = _child(elem, "ValidityPeriod")
    return Situation(
        id=number,
        summary=summary or description or "",
        description=description if description != summary else None,
        severity=_text(elem, "Severity"),
        start=_parse_time(_text(validity, "StartTime")),
        end=_parse_time(_text(validity, "EndTime")),
    )


def parse_stop_events(xml: bytes | str, stop_id: str, language: str = "en") -> Board:
    """Read an OJP 2.0 StopEventDelivery."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as err:
        raise TransitError(f"OJP: unreadable answer ({err})") from err

    delivery = next(iter(_descendants(root, "OJPStopEventDelivery")), None)
    if delivery is None:
        raise TransitError("OJP: no stop event delivery in the answer")
    error = _child(delivery, "ErrorCondition")
    if error is not None:
        message = " ".join(t.strip() for t in error.itertext() if t.strip())
        # "No results" is not a failure: the stop may simply be quiet now.
        if "NO_RESULTS" in message.upper() or "NORESULTS" in message.upper():
            return Board(stop_id, stop_id, OjpClient.source, [])
        raise TransitError(f"OJP: {message}")

    context = _child(delivery, "StopEventResponseContext")
    stop_name = stop_id
    for place in _descendants(context, "Place") if context is not None else []:
        ref = _text(place, "StopPlace", "StopPlaceRef")
        name = _text(place, "StopPlace", "StopPlaceName", "Text") or _text(
            place, "Name", "Text"
        )
        if name and (ref is None or ref.endswith(stop_id) or stop_name == stop_id):
            stop_name = name
            if ref and ref.endswith(stop_id):
                break

    situations = _situations_in(context, language)

    departures: list[Departure] = []
    for result in _children(delivery, "StopEventResult"):
        event = _child(result, "StopEvent")
        call = _child(event, "ThisCall", "CallAtStop")
        service = _child(event, "Service")
        if call is None or service is None:
            continue
        dep = _child(call, "ServiceDeparture")
        planned = _parse_time(_text(dep, "TimetabledTime"))
        if planned is None:
            continue
        expected = _parse_time(_text(dep, "EstimatedTime"))

        pt_mode = (_text(service, "Mode", "PtMode") or "").lower()
        mode = _OJP_MODES.get(pt_mode, "other")
        category = _text(service, "Mode", "ShortName", "Text")
        published = _text(service, "PublishedServiceName", "Text")
        line = published or category or ""
        if mode == "train" and category and line and not line.upper().startswith(
            category.upper()
        ):
            line = f"{category}{line}"
        line = line.replace(" ", "")

        situation_ids = [
            sid
            for ref in _descendants(service, "SituationFullRef")
            if (sid := _text(ref, "SituationNumber"))
        ]
        situation_ids += [
            sid
            for ref in _descendants(call, "SituationFullRef")
            if (sid := _text(ref, "SituationNumber")) and sid not in situation_ids
        ]

        cancelled = (
            (_text(service, "Cancelled") or "").lower() == "true"
            or (_text(call, "NotServicedStop") or "").lower() == "true"
        )
        planned_platform = _text(call, "PlannedQuay", "Text")
        departures.append(
            Departure(
                line=line,
                mode=mode,
                category=category,
                destination=_text(service, "DestinationText", "Text") or "",
                operator=None if (op := _text(service, "OperatorRef") or "").startswith("ojp:") else op or None,
                planned=planned,
                expected=expected,
                platform=_text(call, "EstimatedQuay", "Text") or planned_platform,
                planned_platform=planned_platform,
                cancelled=cancelled,
                realtime=expected is not None,
                situations=situation_ids,
            )
        )

    departures.sort(key=lambda d: d.time)
    return Board(stop_id, stop_name, OjpClient.source, departures, situations)


def _service_info(service: ET.Element) -> tuple[str, str, str | None, str, bool]:
    """Line, mode, category, destination and cancellation of an OJP Service."""
    pt_mode = (_text(service, "Mode", "PtMode") or "").lower()
    mode = _OJP_MODES.get(pt_mode, "other")
    category = _text(service, "Mode", "ShortName", "Text")
    line = _text(service, "PublishedServiceName", "Text") or category or ""
    if mode == "train" and category and line and not line.upper().startswith(category.upper()):
        line = f"{category}{line}"
    cancelled = (_text(service, "Cancelled") or "").lower() == "true"
    return (
        line.replace(" ", ""),
        mode,
        category,
        _text(service, "DestinationText", "Text") or "",
        cancelled,
    )


def _situations_in(elem: ET.Element | None, language: str) -> list[Situation]:
    situations: list[Situation] = []
    for item in _descendants(elem, "PtSituation") if elem is not None else []:
        situation = _parse_situation(item, language)
        if situation and all(s.id != situation.id for s in situations):
            situations.append(situation)
    return situations


def parse_trips(xml: bytes | str, from_id: str, to_id: str, language: str = "en") -> Board:
    """Read an OJP 2.0 TripDelivery."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as err:
        raise TransitError(f"OJP: unreadable answer ({err})") from err
    delivery = next(iter(_descendants(root, "OJPTripDelivery")), None)
    if delivery is None:
        raise TransitError("OJP: no trip delivery in the answer")
    error = _child(delivery, "ErrorCondition")
    if error is not None:
        message = " ".join(t.strip() for t in error.itertext() if t.strip())
        if "NORESULTS" in message.upper().replace("_", ""):
            return Board(from_id, f"{from_id} → {to_id}", OjpClient.source, [])
        raise TransitError(f"OJP: {message}")

    situations = _situations_in(_child(delivery, "TripResponseContext"), language)
    departures: list[Departure] = []
    from_name = to_name = None
    for result in _children(delivery, "TripResult"):
        trip = _child(result, "Trip")
        if trip is None:
            continue
        legs: list[Leg] = []
        first_board: ET.Element | None = None
        last_alight: ET.Element | None = None
        situation_ids: list[str] = []
        for leg in _children(trip, "Leg"):
            timed = _child(leg, "TimedLeg")
            if timed is None:
                walk = _child(leg, "TransferLeg")
                if walk is None:
                    walk = _child(leg, "ContinuousLeg")
                if walk is not None and legs:
                    # A walk between two vehicles; a walk before the first one
                    # is left out, the trip starts at the chosen stop.
                    legs.append(
                        Leg(
                            line="",
                            mode="walk",
                            destination="",
                            board=_text(walk, "LegStart", "Name", "Text") or "",
                            alight=_text(walk, "LegEnd", "Name", "Text") or "",
                        )
                    )
                continue
            board = _child(timed, "LegBoard")
            alight = _child(timed, "LegAlight")
            service = _child(timed, "Service")
            if board is None or alight is None or service is None:
                continue
            line, mode, _category, destination, cancelled = _service_info(service)
            cancelled = cancelled or (_text(timed, "Cancelled") or "").lower() == "true"
            for ref in _descendants(timed, "SituationFullRef"):
                sid = _text(ref, "SituationNumber")
                if sid and sid not in situation_ids:
                    situation_ids.append(sid)
            dep = _child(board, "ServiceDeparture")
            arr = _child(alight, "ServiceArrival")
            legs.append(
                Leg(
                    line=line,
                    mode=mode,
                    destination=destination,
                    board=_text(board, "StopPointName", "Text") or "",
                    alight=_text(alight, "StopPointName", "Text") or "",
                    departure=_parse_time(_text(dep, "EstimatedTime"))
                    or _parse_time(_text(dep, "TimetabledTime")),
                    arrival=_parse_time(_text(arr, "EstimatedTime"))
                    or _parse_time(_text(arr, "TimetabledTime")),
                    platform=_text(board, "EstimatedQuay", "Text")
                    or _text(board, "PlannedQuay", "Text"),
                    cancelled=cancelled,
                )
            )
            if first_board is None:
                first_board = board
            last_alight = alight
        if first_board is None or last_alight is None:
            continue
        dep = _child(first_board, "ServiceDeparture")
        arr = _child(last_alight, "ServiceArrival")
        planned = _parse_time(_text(dep, "TimetabledTime"))
        arrival = _parse_time(_text(arr, "TimetabledTime"))
        if planned is None or arrival is None:
            continue
        from_name = from_name or _text(first_board, "StopPointName", "Text")
        to_name = to_name or _text(last_alight, "StopPointName", "Text")
        expected = _parse_time(_text(dep, "EstimatedTime"))
        planned_platform = _text(first_board, "PlannedQuay", "Text")
        while legs and legs[-1].mode == "walk":
            legs.pop()
        first = legs[0]
        transfers = _text(trip, "Transfers")
        departures.append(
            Departure(
                line=first.line,
                mode=first.mode,
                destination=first.destination,
                planned=planned,
                expected=expected,
                platform=_text(first_board, "EstimatedQuay", "Text") or planned_platform,
                planned_platform=planned_platform,
                cancelled=any(leg.cancelled for leg in legs)
                or (_text(trip, "Cancelled") or "").lower() == "true",
                realtime=expected is not None,
                situations=situation_ids,
                arrival=arrival,
                arrival_expected=_parse_time(_text(arr, "EstimatedTime")),
                transfers=int(transfers)
                if transfers and transfers.isdigit()
                else sum(leg.mode != "walk" for leg in legs) - 1,
                legs=legs,
            )
        )
    departures.sort(key=lambda d: d.time)
    return Board(
        from_id,
        f"{from_name or from_id} → {to_name or to_id}",
        OjpClient.source,
        departures,
        situations,
    )


class OjpClient:
    """opentransportdata.swiss OJP 2.0, needs a free API key."""

    source = "opentransportdata.swiss"

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        """Initialize the client."""
        self._session = session
        self._api_key = api_key.strip()

    async def board(self, stop_id: str, limit: int, language: str = "en") -> Board:
        """Next departures from a stop, with real-time data and disruptions."""
        body = _STOP_EVENT_REQUEST.format(
            lang=escape(language[:2] or "en"),
            now=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            msg=uuid.uuid4().hex[:16],
            stop=escape(stop_id),
            limit=int(limit),
        )
        return parse_stop_events(await self._post(body), stop_id, language)

    async def trip(self, from_id: str, to_id: str, limit: int, language: str = "en") -> Board:
        """Next trips from one stop to another, with real-time data."""
        body = _TRIP_REQUEST.format(
            lang=escape(language[:2] or "en"),
            now=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            msg=uuid.uuid4().hex[:16],
            origin=escape(from_id),
            destination=escape(to_id),
            limit=int(limit),
        )
        return parse_trips(await self._post(body), from_id, to_id, language)

    async def _post(self, body: str) -> bytes:
        try:
            async with self._session.post(
                OJP_URL,
                data=body.encode(),
                timeout=TIMEOUT,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/xml",
                    "User-Agent": USER_AGENT,
                },
            ) as resp:
                if resp.status in (401, 403):
                    raise TransitAuthError("opentransportdata.swiss refused the API key")
                if resp.status == 429:
                    raise TransitError("opentransportdata.swiss rate limit reached")
                resp.raise_for_status()
                return await resp.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TransitError(f"opentransportdata.swiss: {err}") from err
