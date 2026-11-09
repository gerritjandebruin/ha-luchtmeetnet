"""Sensors for Luchtmeetnet stations."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import LuchtmeetnetConfigEntry, LuchtmeetnetCoordinator
from .descriptions import description_for

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuchtmeetnetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one sensor per component measured at the station."""
    coordinator = entry.runtime_data
    async_add_entities(
        LuchtmeetnetSensor(coordinator, formula)
        for formula in sorted(coordinator.components)
    )


class LuchtmeetnetSensor(CoordinatorEntity[LuchtmeetnetCoordinator], SensorEntity):
    """Latest hourly value of one component."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: LuchtmeetnetCoordinator, formula: str) -> None:
        super().__init__(coordinator)
        station = coordinator.station
        self.formula = formula
        self.entity_description = description_for(formula)
        self._attr_unique_id = f"{station.number}_{formula}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, station.number)},
            name=station.location,
            manufacturer=station.organisation or "Luchtmeetnet",
            model=station.number,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        return super().available and self.formula in self.coordinator.data

    @property
    def native_value(self) -> float | None:
        if (m := self.coordinator.data.get(self.formula)) is None:
            return None
        return m.value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if (m := self.coordinator.data.get(self.formula)) is None:
            return None
        start: datetime = m.start
        return {"measured_from": start, "measured_until": start + timedelta(hours=1)}
