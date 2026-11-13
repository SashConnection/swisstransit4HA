"""Constants for Swiss Transit For HA."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "swisstransit4ha"
VERSION: Final = "2026.11.1"
MANUFACTURER: Final = "Swiss public transport"
ATTRIBUTION: Final = "Data: opentransportdata.swiss / transport.opendata.ch"

CONF_STOP_ID: Final = "stop_id"
CONF_STOP_NAME: Final = "stop_name"
CONF_API_KEY: Final = "api_key"
CONF_LIMIT: Final = "limit"
CONF_MODES: Final = "modes"
CONF_LINES: Final = "lines"
CONF_DESTINATION: Final = "destination"
CONF_WALK_TIME: Final = "walk_time"
CONF_DELAY_THRESHOLD: Final = "delay_threshold"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_LIMIT: Final = 10
DEFAULT_WALK_TIME: Final = 0
DEFAULT_DELAY_THRESHOLD: Final = 3
# transport.opendata.ch is a free community service: poll it gently.
DEFAULT_SCAN_INTERVAL_OPEN: Final = 120
DEFAULT_SCAN_INTERVAL_OJP: Final = 60
MIN_SCAN_INTERVAL: Final = 30

# Ask the source for more than shown, so filters still leave enough rows.
FETCH_MARGIN: Final = 3
MAX_FETCH: Final = 60

MODES: Final = ["train", "bus", "tram", "metro", "ship", "cableway", "other"]

FRONTEND_URL: Final = f"/{DOMAIN}_static"
CARD_URL: Final = f"{FRONTEND_URL}/swisstransit-card.js?v={VERSION}"

STALE_AFTER: Final = timedelta(minutes=2)
