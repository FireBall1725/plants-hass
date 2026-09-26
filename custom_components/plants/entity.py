# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Shared entity plumbing: every entity lives on the plant's own device."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .plant import Plant


class PlantEntity(Entity):
    """Base for every entity a plant owns."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, plant: Plant, key: str) -> None:
        self.plant = plant
        self._attr_unique_id = f"{plant.entry.entry_id}_{key}"
        self._attr_translation_key = key
        info = DeviceInfo(
            identifiers={(DOMAIN, plant.entry.entry_id)},
            name=plant.name,
            manufacturer="Plants",
            model=plant.profile.title(),
        )
        # Hang the plant off its sensor device, so the device page links the two.
        if plant.device_id:
            sensor = dr.async_get(plant.hass).async_get(plant.device_id)
            if sensor and sensor.identifiers:
                info["via_device"] = next(iter(sensor.identifiers))
        self._attr_device_info = info

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.plant.add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
