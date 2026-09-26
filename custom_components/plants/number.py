# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""The moisture band: floor and ceiling, tunable per plant."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlantConfigEntry
from .entity import PlantEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    plant = entry.runtime_data
    async_add_entities(
        [BandNumber(plant, "moisture_floor"), BandNumber(plant, "moisture_ceiling")]
    )


class BandNumber(PlantEntity, NumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.BOX

    @property
    def _is_floor(self) -> bool:
        return self.translation_key == "moisture_floor"

    @property
    def native_value(self) -> float:
        return self.plant.floor if self._is_floor else self.plant.ceiling

    async def async_set_native_value(self, value: float) -> None:
        if self._is_floor:
            await self.plant.async_set_band(floor=value)
        else:
            await self.plant.async_set_band(ceiling=value)
