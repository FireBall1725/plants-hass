# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Constants for Plants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

DOMAIN = "plants"

# Config entry data / options.
CONF_DEVICE = "device_id"
CONF_NAME = "name"
CONF_SPECIES = "species"
CONF_PROFILE = "profile"
CONF_THRESHOLD = "threshold"
CONF_ICON = "icon"
CONF_ICON_FILE = "icon_file"
CONF_ICON_MASK = "icon_mask"  # base64 PNG, the processed upload
ICON_CUSTOM = "custom"
# Source entity per reading, found on the sensor device by device class and
# editable in the options.
CONF_MOISTURE = "moisture"
CONF_TEMPERATURE = "temperature"
CONF_ILLUMINANCE = "illuminance"
CONF_CONDUCTIVITY = "conductivity"
CONF_BATTERY = "battery"
READINGS: tuple[str, ...] = (
    CONF_MOISTURE,
    CONF_TEMPERATURE,
    CONF_ILLUMINANCE,
    CONF_CONDUCTIVITY,
    CONF_BATTERY,
)


@dataclass(frozen=True)
class Profile:
    """Starting band and detector threshold for a kind of plant."""

    floor: float
    ceiling: float
    threshold: float  # moisture points a watering must add


# Starting points, not gospel: floor and ceiling become number entities you tune.
# Succulents get a lower threshold because a dry succulent pot rises less when
# watered (Jade went 2 -> 18 in September 2026, where Ginger went 0 -> 54).
PROFILES: dict[str, Profile] = {
    "succulent": Profile(floor=8, ceiling=30, threshold=6),
    "herb": Profile(floor=25, ceiling=60, threshold=10),
    "tropical": Profile(floor=20, ceiling=50, threshold=10),
    "custom": Profile(floor=15, ceiling=60, threshold=10),
}
DEFAULT_PROFILE = "custom"

# Plant marks: the same seven line drawings on the FireLabs display and the card.
# The MDI icon is the nearest stock icon, for HA's own entity rows.
ICONS: dict[str, str] = {
    "succulent": "mdi:sprout-outline",
    "herb": "mdi:leaf",
    "seedling": "mdi:sprout",
    "cactus": "mdi:cactus",
    "fern": "mdi:grass",
    "flowering": "mdi:flower-tulip-outline",
    "tropical": "mdi:palm-tree",
}
PROFILE_ICON: dict[str, str] = {
    "succulent": "succulent",
    "herb": "herb",
    "tropical": "tropical",
    "custom": "seedling",
}


def icon_for(icon: str | None, profile: str | None, has_mask: bool = False) -> str:
    """The plant's mark, or its profile's when unset or no longer offered."""
    if icon in ICONS or (icon == ICON_CUSTOM and has_mask):
        return icon
    return PROFILE_ICON.get(profile or "", "seedling")


# Watering detection. The morning dew moves a dry pot's probe 2-3 points and is
# gone by noon; a watering adds 15-50 and stays.
SMOOTHING = timedelta(minutes=15)
RISE_WINDOW = timedelta(hours=12)
HOLD = timedelta(hours=6)
# A detection this soon after the button is the same water.
MANUAL_GRACE = timedelta(hours=12)

# Status.
STALE_AFTER = timedelta(hours=2)
SOON_DAYS = 3.0
FALLING_PER_DAY = -1.0  # points/day; gentler drift counts as steady

HISTORY_HOURS = 168
HISTORY_TTL = 600  # seconds; hourly statistics only change on the hour

STORAGE_VERSION = 1
SIGNAL_UPDATED = f"{DOMAIN}_updated"
EVENT_WATERED = f"{DOMAIN}_watered"

STATUS_OK = "ok"
STATUS_WATER_SOON = "water_soon"
STATUS_DRY = "dry"
STATUS_STALE = "stale"
STATUS_CHECK_PROBE = "check_probe"
STATUSES = [STATUS_OK, STATUS_WATER_SOON, STATUS_DRY, STATUS_STALE, STATUS_CHECK_PROBE]
