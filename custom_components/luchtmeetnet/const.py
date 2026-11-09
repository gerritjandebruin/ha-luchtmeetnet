"""Constants for the Luchtmeetnet integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "luchtmeetnet"

API_BASE: Final = "https://api.luchtmeetnet.nl/open_api"
ATTRIBUTION: Final = "Data provided by Luchtmeetnet (RIVM and regional environmental services)"

CONF_STATION: Final = "station"
CONF_HISTORY_YEARS: Final = "history_years"
CONF_CORRECT_STATISTICS: Final = "correct_statistics"

DEFAULT_HISTORY_YEARS: Final = 1
MAX_HISTORY_YEARS: Final = 30

UPDATE_INTERVAL: Final = timedelta(minutes=15)
# Window fetched on every update; also used to rewrite recent hourly statistics
# with the measured values (late data and gaps are filled this way).
RECENT_WINDOW: Final = timedelta(hours=48)
# The API refuses ranges longer than seven days.
MAX_REQUEST_WINDOW: Final = timedelta(days=7)

LKI: Final = "LKI"

SERVICE_IMPORT_HISTORY: Final = "import_history"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_START: Final = "start"
ATTR_END: Final = "end"
