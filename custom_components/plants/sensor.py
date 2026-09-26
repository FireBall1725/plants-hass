# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Status, last watered, trend, and floor forecast."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlantConfigEntry
from .const import ICONS, STATUSES
from .entity import PlantEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    plant = entry.runtime_data
    async_add_entities(
        [
            StatusSensor(plant, "status"),
            LastWateredSensor(plant, "last_watered"),
            TrendSensor(plant, "moisture_trend"),
            ForecastSensor(plant, "floor_forecast"),
        ]
    )


class StatusSensor(PlantEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES

    @property
    def native_value(self) -> str:
        return self.plant.status

    @property
    def icon(self) -> str:
        return ICONS.get(self.plant.icon, "mdi:image-filter-center-focus")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        p = self.plant
        return {
            "species": p.species,
            "profile": p.profile,
            "moisture": p.moisture,
            "floor": p.floor,
            "ceiling": p.ceiling,
            "sources": p.sources,
        }


class LastWateredSensor(PlantEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        return self.plant.last_watered

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {"by": self.plant.last_watered_by}
        pending = self.plant.pending
        if pending:
            # A rise has been seen; it counts once it has held for six hours.
            attrs["pending_since"] = pending["since"]
            attrs["pending_rise"] = pending["rise"]
            attrs["confirms_at"] = pending["confirms_at"]
        return attrs


class TrendSensor(PlantEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%/d"
    _attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        return self.plant.trend


class ForecastSensor(PlantEntity, SensorEntity):
    """When moisture reaches the floor at the current rate; unknown unless falling."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        return self.plant.forecast
