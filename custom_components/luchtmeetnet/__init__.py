"""The Luchtmeetnet integration."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .api import LuchtmeetnetClient, LuchtmeetnetError
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_END,
    ATTR_START,
    CONF_HISTORY_YEARS,
    CONF_STATION,
    DOMAIN,
    SERVICE_IMPORT_HISTORY,
)
from .coordinator import STORAGE_VERSION, LuchtmeetnetConfigEntry, LuchtmeetnetCoordinator

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

IMPORT_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_START): cv.date,
        vol.Optional(ATTR_END): cv.date,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services."""

    async def import_history(call: ServiceCall) -> None:
        entry = hass.config_entries.async_get_entry(call.data[ATTR_CONFIG_ENTRY_ID])
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="entry_not_loaded"
            )
        start = _local_midnight(call.data[ATTR_START])
        end = None
        if ATTR_END in call.data:
            end = _local_midnight(call.data[ATTR_END]) + timedelta(days=1)
        if not entry.runtime_data.async_start_history(start, end):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="import_running"
            )

    hass.services.async_register(
        DOMAIN, SERVICE_IMPORT_HISTORY, import_history, schema=IMPORT_HISTORY_SCHEMA
    )
    return True


def _local_midnight(day: date) -> datetime:
    return dt_util.start_of_local_day(day).astimezone(timezone.utc)


async def async_setup_entry(hass: HomeAssistant, entry: LuchtmeetnetConfigEntry) -> bool:
    """Set up a station from a config entry."""
    client = LuchtmeetnetClient(async_get_clientsession(hass))
    try:
        station = await client.async_get_station(entry.data[CONF_STATION])
    except LuchtmeetnetError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = LuchtmeetnetCoordinator(hass, entry, client, station)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    years = entry.data.get(CONF_HISTORY_YEARS, 0)
    if years and not entry.data.get("history_started"):
        # First setup: import the requested years once.
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "history_started": True}
        )
        start = datetime.now(timezone.utc) - timedelta(days=round(365.25 * years))
        coordinator.async_start_history(start)
    else:
        coordinator.async_start_history()  # resume an interrupted import, if any
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LuchtmeetnetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: LuchtmeetnetConfigEntry) -> None:
    """Clean up stored import progress."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
