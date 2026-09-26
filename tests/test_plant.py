# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""A plant end to end: setup, entities, status, the button, the websocket."""

from __future__ import annotations

from custom_components.plants.const import icon_for
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import SENSORS, entity_id_for


async def test_entities_and_status(hass: HomeAssistant, jade: MockConfigEntry) -> None:
    status = hass.states.get(entity_id_for(hass, jade, "sensor", "status"))
    assert status is not None
    assert status.state == "ok"  # 12% against the succulent floor of 8
    assert status.attributes["floor"] == 8
    assert (
        hass.states.get(entity_id_for(hass, jade, "binary_sensor", "needs_water")).state
        == "off"
    )
    assert (
        hass.states.get(entity_id_for(hass, jade, "number", "moisture_floor")).state
        == "8"
    )
    assert (
        hass.states.get(entity_id_for(hass, jade, "number", "moisture_ceiling")).state
        == "30"
    )


async def test_status_follows_the_reading(
    hass: HomeAssistant, jade: MockConfigEntry
) -> None:
    moisture = SENSORS["moisture"][0]
    status_id = entity_id_for(hass, jade, "sensor", "status")

    hass.states.async_set(moisture, "5", {"unit_of_measurement": "%"})
    await hass.async_block_till_done()
    assert hass.states.get(status_id).state == "dry"
    assert (
        hass.states.get(entity_id_for(hass, jade, "binary_sensor", "needs_water")).state
        == "on"
    )

    hass.states.async_set(moisture, "0", {"unit_of_measurement": "%"})
    await hass.async_block_till_done()
    assert hass.states.get(status_id).state == "check_probe"

    hass.states.async_set(moisture, "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(status_id).state == "stale"


async def test_band_is_tunable(hass: HomeAssistant, jade: MockConfigEntry) -> None:
    floor = entity_id_for(hass, jade, "number", "moisture_floor")
    await hass.services.async_call(
        "number", "set_value", {"entity_id": floor, "value": 15}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id_for(hass, jade, "sensor", "status")).state == "dry"


async def test_button_stamps_and_fires_event(
    hass: HomeAssistant, jade: MockConfigEntry
) -> None:
    events = []
    hass.bus.async_listen("plants_watered", events.append)
    button = entity_id_for(hass, jade, "button", "watered")
    before = dt_util.utcnow()
    await hass.services.async_call(
        "button", "press", {"entity_id": button}, blocking=True
    )
    await hass.async_block_till_done()

    last = hass.states.get(entity_id_for(hass, jade, "sensor", "last_watered"))
    assert dt_util.parse_datetime(last.state) >= before.replace(microsecond=0)
    assert last.attributes["by"] == "button"
    assert len(events) == 1
    assert events[0].data["name"] == "Jade"


async def test_legacy_helpers_are_imported(
    hass: HomeAssistant, sensor_device: str
) -> None:
    hass.states.async_set("input_number.jade_moisture_floor", "9.0")
    hass.states.async_set("input_number.jade_moisture_ceiling", "28.0")
    hass.states.async_set("input_datetime.jade_last_watered", "2026-09-21 18:07:47")
    entry = MockConfigEntry(
        domain="plants",
        title="Jade",
        data={"device_id": sensor_device},
        options={
            "name": "Jade",
            "profile": "succulent",
            "threshold": 6,
            **{k: eid for k, (eid, _, _) in SENSORS.items()},
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    plant = entry.runtime_data
    assert plant.floor == 9
    assert plant.ceiling == 28
    assert plant.last_watered_by == "imported"
    assert (
        dt_util.as_local(plant.last_watered).strftime("%Y-%m-%d %H:%M")
        == "2026-09-21 18:07"
    )


async def test_websocket_list(
    hass: HomeAssistant, jade: MockConfigEntry, hass_ws_client
) -> None:
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "plants/list"})
    msg = await client.receive_json()
    assert msg["success"]
    [plant] = msg["result"]
    assert plant["name"] == "Jade"
    assert plant["species"] == "Crassula ovata"
    assert plant["sensor"] == "Plant Sensor 6C31"
    assert plant["readings"]["moisture"]["value"] == 12
    assert plant["readings"]["temperature"]["unit"] == "°C"
    assert plant["status"] == "ok"
    assert plant["icon"] == "succulent"


def test_unknown_icon_falls_back_to_the_profile() -> None:
    assert icon_for("jade", "succulent") == "succulent"
    assert icon_for(None, "herb") == "herb"
    assert icon_for("cactus", "herb") == "cactus"
    assert icon_for("gone", None) == "seedling"
