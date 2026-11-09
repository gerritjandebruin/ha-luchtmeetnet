"""Write measured hourly values into the long-term statistics of the sensors."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    STATISTIC_UNIT_TO_UNIT_CONVERTER,
    async_import_statistics,
)
from homeassistant.components.sensor.const import UNIT_CONVERTERS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api import Measurement
from .descriptions import description_for


def _unit_class(formula: str) -> str | None:
    """Mirror the unit class the sensor recorder derives for this sensor."""
    desc = description_for(formula)
    unit = desc.native_unit_of_measurement
    if (conv := UNIT_CONVERTERS.get(desc.device_class)) and unit in conv.VALID_UNITS:
        return conv.UNIT_CLASS
    if conv := STATISTIC_UNIT_TO_UNIT_CONVERTER.get(unit):
        return conv.UNIT_CLASS
    return None


def entity_ids_by_formula(hass: HomeAssistant, entry_id: str, station: str) -> dict[str, str]:
    """Return {formula: entity_id} for the enabled sensors of an entry."""
    registry = er.async_get(hass)
    prefix = f"{station}_"
    return {
        ent.unique_id.removeprefix(prefix): ent.entity_id
        for ent in er.async_entries_for_config_entry(registry, entry_id)
        if ent.domain == "sensor" and ent.disabled_by is None and ent.unique_id.startswith(prefix)
    }


def import_measurements(
    hass: HomeAssistant,
    entity_ids: dict[str, str],
    measurements: Iterable[Measurement],
    *,
    before: datetime | None = None,
) -> int:
    """Import measurements as hourly statistics; returns the number of rows queued.

    Only hours that started before ``before`` (default: the current hour) are
    written, so the recorder's own compilation of the running hour is untouched.
    """
    if before is None:
        before = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    per_formula: dict[str, dict[datetime, float]] = defaultdict(dict)
    for m in measurements:
        if m.formula in entity_ids and m.start < before:
            per_formula[m.formula][m.start] = m.value

    queued = 0
    for formula, values in per_formula.items():
        desc = description_for(formula)
        metadata = StatisticMetaData(
            mean_type=StatisticMeanType.ARITHMETIC,
            has_sum=False,
            name=None,
            source="recorder",
            statistic_id=entity_ids[formula],
            unit_class=_unit_class(formula),
            unit_of_measurement=desc.native_unit_of_measurement,
        )
        stats = [
            StatisticData(start=start, mean=value, min=value, max=value)
            for start, value in sorted(values.items())
        ]
        async_import_statistics(hass, metadata, stats)
        queued += len(stats)
    return queued


def hour_floor(dt: datetime) -> datetime:
    """Floor a datetime to the whole hour in UTC."""
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
