"""Config flow for Luchtmeetnet."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import LuchtmeetnetClient, LuchtmeetnetError
from .const import (
    CONF_CORRECT_STATISTICS,
    CONF_HISTORY_YEARS,
    CONF_STATION,
    DEFAULT_HISTORY_YEARS,
    DOMAIN,
    MAX_HISTORY_YEARS,
)
from .coordinator import LuchtmeetnetConfigEntry


class LuchtmeetnetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pick a measuring station."""

    VERSION = 1

    def __init__(self) -> None:
        self._stations: dict[str, str] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        client = LuchtmeetnetClient(async_get_clientsession(self.hass))

        if user_input is not None:
            number = user_input[CONF_STATION]
            await self.async_set_unique_id(number)
            self._abort_if_unique_id_configured()
            try:
                station = await client.async_get_station(number)
            except LuchtmeetnetError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=station.location,
                    data={
                        CONF_STATION: number,
                        CONF_HISTORY_YEARS: int(user_input[CONF_HISTORY_YEARS]),
                    },
                    options={CONF_CORRECT_STATISTICS: True},
                )

        if not self._stations:
            try:
                self._stations = await client.async_get_stations()
            except LuchtmeetnetError:
                return self.async_abort(reason="cannot_connect")

        options = [
            SelectOptionDict(value=number, label=f"{location} ({number})")
            for number, location in sorted(self._stations.items(), key=lambda kv: kv[1].lower())
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_STATION): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(CONF_HISTORY_YEARS, default=DEFAULT_HISTORY_YEARS): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=MAX_HISTORY_YEARS, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: LuchtmeetnetConfigEntry) -> LuchtmeetnetOptionsFlow:
        return LuchtmeetnetOptionsFlow()


class LuchtmeetnetOptionsFlow(OptionsFlowWithReload):
    """Options for a station."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CORRECT_STATISTICS,
                    default=self.config_entry.options.get(CONF_CORRECT_STATISTICS, True),
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
