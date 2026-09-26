# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Logbook lines for watering events."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN, EVENT_WATERED


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, Any]]], None],
) -> None:
    @callback
    def describe(event: Event) -> dict[str, Any]:
        data = event.data
        if data.get("by") == "button":
            message = "was marked as watered"
        elif data.get("rise") is not None:
            message = f"was watered (moisture +{data['rise']} points)"
        else:
            message = "was watered"
        return {"name": data.get("name", "Plant"), "message": message}

    async_describe_event(DOMAIN, EVENT_WATERED, describe)
