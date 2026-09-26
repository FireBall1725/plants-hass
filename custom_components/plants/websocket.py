# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Websocket API for cards: the plants, and their curves."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, HISTORY_HOURS


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_history)


def _plants(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.get(DOMAIN, {}).get("plants", {})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/list"})
@callback
def ws_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Every plant: readings with their ages, band, status, trend, last watered."""
    connection.send_result(msg["id"], [p.snapshot() for p in _plants(hass).values()])


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/history",
        vol.Optional("entry_ids"): [str],
        vol.Optional("hours", default=HISTORY_HOURS): vol.All(
            int, vol.Range(1, 24 * 31)
        ),
    }
)
@websocket_api.async_response
async def ws_history(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Hourly mean moisture per plant, from long-term statistics."""
    wanted = msg.get("entry_ids") or list(_plants(hass))
    out: dict[str, Any] = {"start": None, "series": {}}
    for entry_id in wanted:
        plant = _plants(hass).get(entry_id)
        if plant is None:
            continue
        start, series = await plant.async_history(msg["hours"])
        out["start"] = start.isoformat()
        out["series"][entry_id] = series
    connection.send_result(msg["id"], out)
