# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Watered now: the manual stamp."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlantConfigEntry
from .entity import PlantEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([WateredButton(entry.runtime_data, "watered")])


class WateredButton(PlantEntity, ButtonEntity):
    _attr_icon = "mdi:watering-can"

    async def async_press(self) -> None:
        await self.plant.async_mark_watered()
