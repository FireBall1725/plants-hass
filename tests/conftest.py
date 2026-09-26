# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Shared fixtures: a fake Mi Flora device with five sensors, and a plant on it."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from custom_components.plants.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

SENSORS = {
    "moisture": ("sensor.plant_sensor_6c31_moisture", "12", "%"),
    "temperature": ("sensor.plant_sensor_6c31_temperature", "20.3", "°C"),
    "illuminance": ("sensor.plant_sensor_6c31_illuminance", "118", "lx"),
    "conductivity": ("sensor.plant_sensor_6c31_conductivity", "22", "µS/cm"),
    "battery": ("sensor.plant_sensor_6c31_battery", "98", "%"),
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> Generator[None]:
    """Let the test harness load custom_components."""
    yield


@pytest.fixture
def sensor_device(hass: HomeAssistant) -> str:
    """A Mi Flora-like device renamed "Jade", with its five sensors registered."""
    source = MockConfigEntry(domain="xiaomi_ble", title="Plant Sensor 6C31")
    source.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={("bluetooth", "C4:7C:8D:6A:6C:31")},
        name="Plant Sensor 6C31",
        model="HHCCJCY01",
    )
    dr.async_get(hass).async_update_device(device.id, name_by_user="Jade")
    reg = er.async_get(hass)
    for key, (entity_id, state, unit) in SENSORS.items():
        object_id = entity_id.split(".")[1]
        reg.async_get_or_create(
            "sensor",
            "xiaomi_ble",
            object_id,
            suggested_object_id=object_id,
            device_id=device.id,
            config_entry=source,
            original_device_class=key,
        )
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})
    return device.id


@pytest.fixture
async def jade(hass: HomeAssistant, sensor_device: str) -> MockConfigEntry:
    """A loaded plant entry for the device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Jade",
        data={"device_id": sensor_device},
        options={
            "name": "Jade",
            "species": "Crassula ovata",
            "profile": "succulent",
            "threshold": 6,
            **{key: entity_id for key, (entity_id, _, _) in SENSORS.items()},
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity_id_for(
    hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str
) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{entry.entry_id}_{key}"
    )
    assert entity_id is not None, f"no {platform} {key}"
    return entity_id
