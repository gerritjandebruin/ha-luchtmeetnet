"""Sensor descriptions per Luchtmeetnet component."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfDensity

from .const import LKI

UG = UnitOfDensity.MICROGRAMS_PER_CUBIC_METER

# Components without a device class that have a translated name in strings.json.
_TRANSLATED = {"nox", "nh3", "h2s", "c6h6", "c7h8", "c8h10", "c10h8"}

_DEVICE_CLASSES: dict[str, SensorDeviceClass] = {
    "PM25": SensorDeviceClass.PM25,
    "PM10": SensorDeviceClass.PM10,
    "NO2": SensorDeviceClass.NITROGEN_DIOXIDE,
    "NO": SensorDeviceClass.NITROGEN_MONOXIDE,
    "O3": SensorDeviceClass.OZONE,
    "SO2": SensorDeviceClass.SULPHUR_DIOXIDE,
    "CO": SensorDeviceClass.CO,
}

_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    LKI: SensorEntityDescription(
        key=LKI,
        translation_key="lki",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    # Ultrafine particles: number concentration, not mass.
    "PS": SensorEntityDescription(
        key="PS",
        translation_key="ps",
        native_unit_of_measurement="particles/cm³",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
}


def description_for(formula: str) -> SensorEntityDescription:
    """Return the entity description for a component formula."""
    if formula in _DESCRIPTIONS:
        return _DESCRIPTIONS[formula]
    if formula in _DEVICE_CLASSES:
        return SensorEntityDescription(
            key=formula,
            device_class=_DEVICE_CLASSES[formula],
            native_unit_of_measurement=UG,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        )
    # NOx, NH3, H2S, benzene, toluene, xylene, naphthalene; unknown ones by formula.
    translated = formula.lower() in _TRANSLATED
    return SensorEntityDescription(
        key=formula,
        translation_key=formula.lower() if translated else None,
        name=None if translated else formula,
        native_unit_of_measurement=UG,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    )
