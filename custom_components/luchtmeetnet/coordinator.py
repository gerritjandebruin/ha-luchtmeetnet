"""Coordinator and history import for Luchtmeetnet."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LuchtmeetnetClient, LuchtmeetnetError, Measurement, Station
from .const import (
    CONF_CORRECT_STATISTICS,
    DOMAIN,
    LKI,
    MAX_REQUEST_WINDOW,
    RECENT_WINDOW,
    UPDATE_INTERVAL,
)
from .statistics import entity_ids_by_formula, hour_floor, import_measurements

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
# Import statistics in batches of this many weeks of data.
IMPORT_BATCH_WEEKS = 8

type LuchtmeetnetConfigEntry = ConfigEntry[LuchtmeetnetCoordinator]


class LuchtmeetnetCoordinator(DataUpdateCoordinator[dict[str, Measurement]]):
    """Fetches the latest measurements of one station."""

    config_entry: LuchtmeetnetConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LuchtmeetnetConfigEntry,
        client: LuchtmeetnetClient,
        station: Station,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {station.number}",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.station = station
        self.components: set[str] = set(station.components) | {LKI}
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._history_task: asyncio.Task[None] | None = None

    async def _async_update_data(self) -> dict[str, Measurement]:
        end = hour_floor(datetime.now(timezone.utc)) + timedelta(hours=1)
        try:
            rows = await self.client.async_get_measurements(
                self.station.number, end - RECENT_WINDOW, end
            )
        except LuchtmeetnetError as err:
            raise UpdateFailed(str(err)) from err

        latest: dict[str, Measurement] = {}
        for m in rows:
            if m.formula not in latest or m.start > latest[m.formula].start:
                latest[m.formula] = m
        self.components |= set(latest)

        if self.config_entry.options.get(CONF_CORRECT_STATISTICS, True):
            # Replace the hourly statistics of the recent window with the
            # measured values: the recorder averages a state that lags about an
            # hour behind and misses values published late.
            self._import(rows)
        return latest

    @callback
    def _import(self, rows: list[Measurement], before: datetime | None = None) -> int:
        entity_ids = entity_ids_by_formula(
            self.hass, self.config_entry.entry_id, self.station.number
        )
        return import_measurements(self.hass, entity_ids, rows, before=before)

    # --- history -----------------------------------------------------------

    @callback
    def async_start_history(self, start: datetime | None = None, end: datetime | None = None) -> bool:
        """Start (or resume) importing history in the background.

        Without arguments a pending import from the store is resumed.
        Returns False when an import is already running.
        """
        if self._history_task and not self._history_task.done():
            return False
        self._history_task = self.config_entry.async_create_background_task(
            self.hass,
            self._async_history(start, end),
            f"{DOMAIN} history {self.station.number}",
        )
        return True

    async def _async_history(self, start: datetime | None, end: datetime | None) -> None:
        if start is not None:
            state = {
                "start": hour_floor(start).isoformat(),
                "end": hour_floor(end or datetime.now(timezone.utc) - RECENT_WINDOW).isoformat(),
            }
            state["cursor"] = state["start"]
            await self._store.async_save(state)
        else:
            state = await self._store.async_load() or {}
            if not state or state.get("cursor") is None:
                return

        cursor = datetime.fromisoformat(state["cursor"])
        stop = datetime.fromisoformat(state["end"])
        _LOGGER.info(
            "Importing Luchtmeetnet history for %s from %s to %s",
            self.station.number, cursor, stop,
        )
        total = 0
        while cursor < stop:
            upper = min(cursor + MAX_REQUEST_WINDOW * IMPORT_BATCH_WEEKS, stop)
            try:
                rows = await self.client.async_get_measurements(self.station.number, cursor, upper)
            except LuchtmeetnetError as err:
                _LOGGER.warning("History import paused at %s: %s", cursor, err)
                return  # resumed on next start or service call
            total += self._import(rows, before=upper)
            cursor = upper
            state["cursor"] = cursor.isoformat()
            await self._store.async_save(state)
        state["cursor"] = None
        await self._store.async_save(state)
        _LOGGER.info(
            "Luchtmeetnet history for %s imported: %s hourly values", self.station.number, total
        )