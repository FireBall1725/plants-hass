# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Plants: one object per plant.

A plant used to be a pile of helpers: a smoothing filter, a statistics window, a
floor and ceiling, a last-watered date and button, template sensors, and a branch
of a detection automation. Each config entry here is one plant made by picking its
sensor device. It owns its thresholds and watering record, detects watering from
the moisture curve, and serves the same picture of itself to entities, Lovelace
cards (over websocket) and other integrations (hass.data).
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .frontend import async_register_cards
from .plant import Plant
from .websocket import async_register_websocket

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PlantConfigEntry = ConfigEntry[Plant]


def plants(hass: HomeAssistant) -> dict[str, Plant]:
    """Every loaded plant, by config entry id. Other integrations read this."""
    return hass.data.setdefault(DOMAIN, {}).setdefault("plants", {})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the websocket API and the cards once for all plants."""
    async_register_websocket(hass)
    await async_register_cards(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PlantConfigEntry) -> bool:
    """Set up one plant."""
    plant = Plant(hass, entry)
    await plant.async_setup()
    entry.runtime_data = plant
    plants(hass)[entry.entry_id] = plant

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PlantConfigEntry) -> bool:
    """Tear down one plant."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
        plants(hass).pop(entry.entry_id, None)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: PlantConfigEntry) -> None:
    """Options changed (sources, threshold, profile): rebuild the plant."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: PlantConfigEntry) -> None:
    """Drop the stored record when a plant is deleted."""
    from homeassistant.helpers.storage import Store  # noqa: PLC0415

    from .const import STORAGE_VERSION  # noqa: PLC0415

    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
