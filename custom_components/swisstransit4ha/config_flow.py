"""Config flow for Swiss Transit For HA."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import OjpClient, OpenTransportClient, Stop, TransitAuthError, TransitError
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
    KIND_TRIP,
    MIN_SCAN_INTERVAL,
    MODES,
)

_LOGGER = logging.getLogger(__name__)

CONF_QUERY = "query"
CONF_FROM_QUERY = "from_query"
CONF_TO_QUERY = "to_query"

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


async def _check_key(hass: HomeAssistant, api_key: str, stop_id: str) -> str | None:
    """Return an error code, or None when the key works."""
    if not api_key:
        return None
    try:
        await OjpClient(async_get_clientsession(hass), api_key).board(stop_id, 1)
    except TransitAuthError:
        return "invalid_api_key"
    except TransitError as err:
        _LOGGER.warning("Could not check the API key: %s", err)
        return "cannot_connect"
    return None


def _stop_options(stops: dict[str, Stop]) -> list[SelectOptionDict]:
    return [
        SelectOptionDict(value=s.id, label=s.name if not s.mode else f"{s.name} ({s.mode})")
        for s in stops.values()
    ]


async def _search(hass: HomeAssistant, query: str) -> dict[str, Stop]:
    stops = await OpenTransportClient(async_get_clientsession(hass)).search(query.strip())
    return {s.id: s for s in stops}


def _filters_schema(values: Mapping[str, Any], trip: bool = False) -> vol.Schema:
    """Filters shared by the first setup and the options."""
    has_key = bool((values.get(CONF_API_KEY) or "").strip())
    default_interval = DEFAULT_SCAN_INTERVAL_OJP if has_key else DEFAULT_SCAN_INTERVAL_OPEN
    fields: dict[Any, Any] = {
        vol.Optional(CONF_LIMIT, default=values.get(CONF_LIMIT, DEFAULT_LIMIT)): NumberSelector(
            NumberSelectorConfig(
                min=1, max=16 if trip else 30, step=1, mode=NumberSelectorMode.BOX
            )
        ),
    }
    if not trip:
        fields.update(_departure_filters(values))
    fields.update(_common_filters(values, default_interval))
    return vol.Schema(fields)


def _departure_filters(values: Mapping[str, Any]) -> dict[Any, Any]:
    """Filters that only make sense for a departure board."""
    return {
        vol.Optional(CONF_MODES, default=values.get(CONF_MODES) or []): SelectSelector(
            SelectSelectorConfig(
                options=MODES,
                multiple=True,
                mode=SelectSelectorMode.LIST,
                translation_key="mode",
            )
        ),
        vol.Optional(
            CONF_LINES, description={"suggested_value": values.get(CONF_LINES)}
        ): TextSelector(),
        vol.Optional(
            CONF_DESTINATION, description={"suggested_value": values.get(CONF_DESTINATION)}
        ): TextSelector(),
    }


def _common_filters(values: Mapping[str, Any], default_interval: int) -> dict[Any, Any]:
    return {
        vol.Optional(
            CONF_WALK_TIME, default=values.get(CONF_WALK_TIME, DEFAULT_WALK_TIME)
        ): NumberSelector(
            NumberSelectorConfig(
                min=0, max=60, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX
            )
        ),
        vol.Optional(
            CONF_DELAY_THRESHOLD,
            default=values.get(CONF_DELAY_THRESHOLD, DEFAULT_DELAY_THRESHOLD),
        ): NumberSelector(
            NumberSelectorConfig(
                min=1, max=60, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX
            )
        ),
        vol.Optional(
            CONF_SCAN_INTERVAL,
            default=values.get(CONF_SCAN_INTERVAL, default_interval),
        ): NumberSelector(
            NumberSelectorConfig(
                min=MIN_SCAN_INTERVAL,
                max=900,
                step=10,
                unit_of_measurement="s",
                mode=NumberSelectorMode.BOX,
            )
        ),
    }


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Store numbers as int and drop empty texts."""
    out: dict[str, Any] = {}
    for key, value in user_input.items():
        if isinstance(value, float):
            value = int(value)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        out[key] = value
    return out


class TransitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Choose a stop or station."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._stops: dict[str, Stop] = {}
        self._to_stops: dict[str, Stop] = {}
        self._stop: Stop | None = None
        self._to_stop: Stop | None = None
        self._api_key: str = ""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options: filters and API key."""
        return TransitOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Departure board of a stop, or trips from A to B."""
        return self.async_show_menu(step_id="user", menu_options=["departures", "trip"])

    async def async_step_departures(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search a stop by name."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._api_key = (user_input.get(CONF_API_KEY) or "").strip()
            query = user_input[CONF_QUERY].strip()
            try:
                stops = await OpenTransportClient(async_get_clientsession(self.hass)).search(query)
            except TransitError as err:
                _LOGGER.warning("Stop search failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not stops:
                    errors[CONF_QUERY] = "no_stop"
                else:
                    self._stops = {s.id: s for s in stops}
                    return await self.async_step_stop()

        return self.async_show_form(
            step_id="departures",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_QUERY): TextSelector(),
                    vol.Optional(CONF_API_KEY): _PASSWORD,
                }
            ),
            errors=errors,
        )

    async def async_step_stop(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick one of the stops found."""
        errors: dict[str, str] = {}
        if user_input is not None:
            stop = self._stops[user_input[CONF_STOP_ID]]
            if error := await _check_key(self.hass, self._api_key, stop.id):
                errors["base"] = error
            else:
                self._stop = stop
                return await self.async_step_filters()

        options = _stop_options(self._stops)
        return self.async_show_form(
            step_id="stop",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP_ID, default=options[0]["value"]): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_filters(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optional filters: lines, direction, walking time."""
        assert self._stop is not None
        if user_input is not None:
            options = _clean(user_input)
            if self._api_key:
                options[CONF_API_KEY] = self._api_key
            title = self._stop.name
            if dest := options.get(CONF_DESTINATION):
                title = f"{title} → {dest}"
            return self.async_create_entry(
                title=title,
                data={CONF_STOP_ID: self._stop.id, CONF_STOP_NAME: self._stop.name},
                options=options,
            )
        return self.async_show_form(
            step_id="filters",
            data_schema=_filters_schema({CONF_API_KEY: self._api_key}),
            description_placeholders={"stop": self._stop.name},
        )

    async def async_step_trip(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Search the departure and arrival stops."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._api_key = (user_input.get(CONF_API_KEY) or "").strip()
            try:
                self._stops = await _search(self.hass, user_input[CONF_FROM_QUERY])
                self._to_stops = await _search(self.hass, user_input[CONF_TO_QUERY])
            except TransitError as err:
                _LOGGER.warning("Stop search failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not self._stops:
                    errors[CONF_FROM_QUERY] = "no_stop"
                if not self._to_stops:
                    errors[CONF_TO_QUERY] = "no_stop"
                if not errors:
                    return await self.async_step_trip_stops()

        return self.async_show_form(
            step_id="trip",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FROM_QUERY): TextSelector(),
                    vol.Required(CONF_TO_QUERY): TextSelector(),
                    vol.Optional(CONF_API_KEY): _PASSWORD,
                }
            ),
            errors=errors,
        )

    async def async_step_trip_stops(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the departure and arrival stops among those found."""
        errors: dict[str, str] = {}
        if user_input is not None:
            stop = self._stops[user_input[CONF_STOP_ID]]
            to_stop = self._to_stops[user_input[CONF_TO_ID]]
            if stop.id == to_stop.id:
                errors["base"] = "same_stop"
            elif error := await _check_key(self.hass, self._api_key, stop.id):
                errors["base"] = error
            else:
                self._stop, self._to_stop = stop, to_stop
                return await self.async_step_trip_filters()

        from_options = _stop_options(self._stops)
        to_options = _stop_options(self._to_stops)
        return self.async_show_form(
            step_id="trip_stops",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP_ID, default=from_options[0]["value"]): SelectSelector(
                        SelectSelectorConfig(options=from_options, mode=SelectSelectorMode.DROPDOWN)
                    ),
                    vol.Required(CONF_TO_ID, default=to_options[0]["value"]): SelectSelector(
                        SelectSelectorConfig(options=to_options, mode=SelectSelectorMode.DROPDOWN)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_trip_filters(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Number of trips, walking time."""
        assert self._stop is not None and self._to_stop is not None
        if user_input is not None:
            options = _clean(user_input)
            if self._api_key:
                options[CONF_API_KEY] = self._api_key
            return self.async_create_entry(
                title=f"{self._stop.name} → {self._to_stop.name}",
                data={
                    CONF_KIND: KIND_TRIP,
                    CONF_STOP_ID: self._stop.id,
                    CONF_STOP_NAME: self._stop.name,
                    CONF_TO_ID: self._to_stop.id,
                    CONF_TO_NAME: self._to_stop.name,
                },
                options=options,
            )
        return self.async_show_form(
            step_id="trip_filters",
            data_schema=_filters_schema({CONF_API_KEY: self._api_key, CONF_LIMIT: 5}, trip=True),
            description_placeholders={"from": self._stop.name, "to": self._to_stop.name},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The API key was refused."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new key, or none to fall back to the free source."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = (user_input.get(CONF_API_KEY) or "").strip()
            if error := await _check_key(self.hass, api_key, entry.data[CONF_STOP_ID]):
                errors["base"] = error
            else:
                options = {k: v for k, v in entry.options.items() if k != CONF_API_KEY}
                if api_key:
                    options[CONF_API_KEY] = api_key
                self.hass.config_entries.async_update_entry(entry, options=options)
                return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_API_KEY): _PASSWORD}),
            errors=errors,
        )


class TransitOptionsFlow(OptionsFlow):
    """Change filters or the API key."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the options."""
        errors: dict[str, str] = {}
        current = dict(self.config_entry.options)
        if user_input is not None:
            options = _clean(user_input)
            api_key = options.get(CONF_API_KEY, "")
            if api_key and api_key != current.get(CONF_API_KEY):
                if error := await _check_key(
                    self.hass, api_key, self.config_entry.data[CONF_STOP_ID]
                ):
                    errors["base"] = error
            if not errors:
                return self.async_create_entry(data=options)
            current = {**current, **user_input}

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_API_KEY, description={"suggested_value": current.get(CONF_API_KEY)}
                ): _PASSWORD,
            }
        ).extend(
            _filters_schema(current, trip=self.config_entry.data.get(CONF_KIND) == KIND_TRIP).schema
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
