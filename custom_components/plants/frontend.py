# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Serve the Lovelace cards from the integration, so HACS installs them with it."""

from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

URL_BASE = "/plants_frontend"
CARD = "plants-card.js"


def _digest(path: Path) -> str:
    return hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()[:10]


async def async_register_cards(hass: HomeAssistant) -> None:
    """Serve frontend/ and load the card module on every dashboard."""
    if hass.http is None or "frontend" not in hass.config.components:
        return  # headless (tests): nothing to serve to
    folder = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL_BASE, str(folder), cache_headers=False)]
    )
    # The query changes with the file, so a new release isn't hidden by the cache.
    digest = await hass.async_add_executor_job(_digest, folder / CARD)
    add_extra_js_url(hass, f"{URL_BASE}/{CARD}?v={digest}")
