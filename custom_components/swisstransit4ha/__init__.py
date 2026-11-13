"""The Swiss Transit For HA integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CARD_URL, DOMAIN, FRONTEND_URL
from .coordinator import TransitConfigEntry, TransitCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the departure board card and load it on every dashboard."""
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                FRONTEND_URL, str(Path(__file__).parent / "frontend"), cache_headers=False
            )
        ]
    )
    add_extra_js_url(hass, CARD_URL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TransitConfigEntry) -> bool:
    """Set up one stop."""
    coordinator = TransitCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: TransitConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TransitConfigEntry) -> bool:
    """Unload a stop."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
