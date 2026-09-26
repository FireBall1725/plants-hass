# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Needs water: the one to notify on."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlantConfigEntry
from .entity import PlantEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([NeedsWater(entry.runtime_data, "needs_water")])


class NeedsWater(PlantEntity, BinarySensorEntity):
    """On while moisture is under the floor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return self.plant.needs_water
