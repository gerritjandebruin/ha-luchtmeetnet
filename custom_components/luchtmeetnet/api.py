"""Minimal async client for the Luchtmeetnet open API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Any

import aiohttp

from .const import API_BASE, MAX_REQUEST_WINDOW

_LOGGER = logging.getLogger(__name__)

# The API rate limits aggressively (HTTP 429); keep requests spaced out.
_MIN_INTERVAL = 1.0
_MAX_RETRIES = 8
_MAX_FAILURES = 3


class LuchtmeetnetError(Exception):
    """Error talking to the Luchtmeetnet API."""


@dataclass(frozen=True, slots=True)
class Measurement:
    """One hourly measurement; ``start`` is the beginning of the hour (UTC)."""

    formula: str
    value: float
    start: datetime


@dataclass(frozen=True, slots=True)
class Station:
    """Station metadata."""

    number: str
    location: str
    municipality: str | None
    organisation: str | None
    components: list[str]
    latitude: float | None
    longitude: float | None


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(row: dict[str, Any]) -> Measurement | None:
    if row.get("value") is None:
        return None
    # timestamp_measured is the END of the hour; older data lacks the
    # explicit start/end fields, so derive the start from it.
    end = datetime.fromisoformat(row["timestamp_measured"])
    return Measurement(row["formula"], float(row["value"]), end - timedelta(hours=1))


class LuchtmeetnetClient:
    """Client for api.luchtmeetnet.nl."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{API_BASE}/{path}"
        failures = 0  # server and network errors; rate limiting is retried longer
        for attempt in range(_MAX_RETRIES):
            async with self._lock:
                wait = self._last + _MIN_INTERVAL - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last = time.monotonic()
                try:
                    async with self._session.get(
                        url, params=params, timeout=aiohttp.ClientTimeout(total=60)
                    ) as resp:
                        status: int | str = resp.status
                        if resp.status == 200:
                            return await resp.json(content_type=None)
                except (aiohttp.ClientError, TimeoutError) as err:
                    status = repr(err)
            if status != 429:
                failures += 1
                if isinstance(status, int) and status < 500 or failures >= _MAX_FAILURES:
                    raise LuchtmeetnetError(f"Request to {path} failed: {status}")
            delay = min(15 * (attempt + 1), 120)
            _LOGGER.debug("Luchtmeetnet %s gave %s, retrying in %s s", path, status, delay)
            await asyncio.sleep(delay)
        raise LuchtmeetnetError(f"Request to {path} still rate limited after {_MAX_RETRIES} attempts")

    async def _paged(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            data = await self._get(path, {**params, "page": page})
            rows.extend(data.get("data", []))
            if page >= data.get("pagination", {}).get("last_page", 0):
                return rows
            page += 1

    async def async_get_stations(self) -> dict[str, str]:
        """Return all stations as {number: location}."""
        rows = await self._paged("stations", {})
        return {r["number"]: r["location"] for r in rows}

    async def async_get_station(self, number: str) -> Station:
        """Return metadata of one station."""
        data = (await self._get(f"stations/{number}")).get("data") or {}
        coords = (data.get("geometry") or {}).get("coordinates") or [None, None]
        return Station(
            number=number,
            location=data.get("location") or number,
            municipality=data.get("municipality"),
            organisation=data.get("organisation"),
            components=list(data.get("components") or []),
            longitude=coords[0],
            latitude=coords[1],
        )

    async def async_get_measurements(
        self, number: str, start: datetime, end: datetime, *, lki: bool = True
    ) -> list[Measurement]:
        """Return all measurements of a station with an hour start in [start, end)."""
        out: list[Measurement] = []
        # timestamp_measured is the end of the hour, so shift the query by one hour.
        cursor = start + timedelta(hours=1)
        stop = end + timedelta(hours=1)
        while cursor < stop:
            upper = min(cursor + MAX_REQUEST_WINDOW, stop)
            params = {"station_number": number, "start": _fmt(cursor), "end": _fmt(upper)}
            rows = await self._paged("measurements", params)
            if lki:
                rows += await self._paged("lki", params)
            for row in rows:
                if (m := _parse(row)) is not None and start <= m.start < end:
                    out.append(m)
            # end is inclusive in the API; move one second past it
            cursor = upper + timedelta(seconds=1)
        return out
