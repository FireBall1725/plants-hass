# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""One plant: its sensors, thresholds, watering record, and what they add up to."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    CONF_DEVICE,
    CONF_ICON,
    CONF_ICON_MASK,
    CONF_MOISTURE,
    CONF_NAME,
    CONF_PROFILE,
    CONF_SPECIES,
    CONF_THRESHOLD,
    DEFAULT_PROFILE,
    DOMAIN,
    EVENT_WATERED,
    FALLING_PER_DAY,
    HISTORY_HOURS,
    HOLD,
    ICON_CUSTOM,
    PROFILES,
    READINGS,
    RISE_WINDOW,
    SIGNAL_UPDATED,
    SOON_DAYS,
    STALE_AFTER,
    STATUS_CHECK_PROBE,
    STATUS_DRY,
    STATUS_OK,
    STATUS_STALE,
    STATUS_WATER_SOON,
    STORAGE_VERSION,
    icon_for,
)
from .detector import WateringDetector
from .history import async_hourly_means, async_recent_states
from .icon import display_mask

_LOGGER = logging.getLogger(__name__)

_UNUSABLE = (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE)
_REFRESH = timedelta(minutes=10)


def _mean(values: list[float | None], lo: int, hi: int) -> float | None:
    picked = [v for v in values[max(lo, 0) : max(hi, 0)] if v is not None]
    return sum(picked) / len(picked) if picked else None


class Plant:
    """The runtime object behind one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        cfg = {**entry.data, **entry.options}
        self.device_id: str | None = entry.data.get(CONF_DEVICE)
        self.name: str = cfg.get(CONF_NAME) or entry.title
        self.species: str = cfg.get(CONF_SPECIES) or ""
        self.profile: str = cfg.get(CONF_PROFILE) or DEFAULT_PROFILE
        base = PROFILES.get(self.profile, PROFILES[DEFAULT_PROFILE])
        mask: str | None = cfg.get(CONF_ICON_MASK)
        self.icon: str = icon_for(cfg.get(CONF_ICON), self.profile, bool(mask))
        # A custom mark: the card draws the PNG, the FireLabs display the A8 bytes.
        self.icon_image: str | None = None
        self.icon_display: str | None = None
        if self.icon == ICON_CUSTOM and mask:
            self.icon_image = f"data:image/png;base64,{mask}"
            self.icon_display = display_mask(mask)
        self.threshold: float = float(cfg.get(CONF_THRESHOLD) or base.threshold)
        self.sources: dict[str, str] = {r: cfg[r] for r in READINGS if cfg.get(r)}

        self.floor: float = base.floor
        self.ceiling: float = base.ceiling
        self.last_watered: datetime | None = None
        self.last_watered_by: str | None = None  # detected, button, imported

        self.trend: float | None = None  # points/day over the last three days
        self.forecast: datetime | None = None  # when moisture reaches the floor

        self._detector = WateringDetector(self.threshold)
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._unsubs: list[CALLBACK_TYPE] = []

    # ---------- lifecycle ----------

    async def async_setup(self) -> None:
        """Load the record, catch up on the last few hours, then start listening."""
        stored = await self._store.async_load()
        if stored:
            self.floor = stored.get("floor", self.floor)
            self.ceiling = stored.get("ceiling", self.ceiling)
            self.last_watered = dt_util.parse_datetime(stored.get("last_watered") or "")
            self.last_watered_by = stored.get("last_watered_by")
        else:
            self._import_legacy()
            self._save()

        await self._async_replay()

        self._unsubs.append(
            async_track_state_change_event(
                self.hass, list(self.sources.values()), self._handle_state
            )
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._async_tick, _REFRESH)
        )
        await self._async_refresh_trend()

    async def async_shutdown(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._store.async_save(self._record())

    def _import_legacy(self) -> None:
        """Pick up the helpers this integration replaces, if they exist.

        Before this integration a plant was a set of helpers named after it:
        input_number.<name>_moisture_floor / _ceiling and
        input_datetime.<name>_last_watered.
        """
        slug = slugify(self.name)
        for attr, entity_id in (
            ("floor", f"input_number.{slug}_moisture_floor"),
            ("ceiling", f"input_number.{slug}_moisture_ceiling"),
        ):
            value = self._num(self.hass.states.get(entity_id))
            if value is not None:
                setattr(self, attr, value)
        watered = self.hass.states.get(f"input_datetime.{slug}_last_watered")
        if watered is not None and watered.state not in _UNUSABLE:
            parsed = dt_util.parse_datetime(watered.state)
            if parsed is not None:
                if parsed.tzinfo is None:  # input_datetime states are naive local time
                    parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
                self.last_watered = dt_util.as_utc(parsed)
                self.last_watered_by = "imported"
        if self.last_watered_by == "imported":
            _LOGGER.info(
                "%s: imported floor %s, ceiling %s, last watered %s from helpers",
                self.name,
                self.floor,
                self.ceiling,
                self.last_watered,
            )

    async def _async_replay(self) -> None:
        """Replay the last window + hold, so a restart mid-watering still finds it."""
        moisture = self.sources.get(CONF_MOISTURE)
        if not moisture:
            return
        states = await async_recent_states(self.hass, moisture, RISE_WINDOW + HOLD)
        if self.last_watered_by == "button" and self.last_watered:
            self._detector.mark_watered(self.last_watered)
        for state in states:
            value = self._num(state)
            if value is None:
                continue
            watering = self._detector.feed(state.last_changed, value)
            if watering and (
                self.last_watered is None
                or watering.at > self.last_watered + timedelta(hours=1)
            ):
                self._stamp(watering.at, "detected", watering.rise)

    # ---------- inputs ----------

    @callback
    def _handle_state(self, event: Event[EventStateChangedData]) -> None:
        new = event.data["new_state"]
        if new is not None and new.entity_id == self.sources.get(CONF_MOISTURE):
            value = self._num(new)
            if value is not None:
                watering = self._detector.feed(new.last_changed, value)
                if watering and (
                    self.last_watered is None or watering.at > self.last_watered
                ):
                    self._stamp(watering.at, "detected", watering.rise)
        self._recompute_forecast()
        self._signal()

    async def _async_tick(self, _now: datetime) -> None:
        await self._async_refresh_trend()

    async def _async_refresh_trend(self) -> None:
        moisture = self.sources.get(CONF_MOISTURE)
        if not moisture:
            return
        _, series = await async_hourly_means(self.hass, [moisture], HISTORY_HOURS)
        values = series.get(moisture, [])
        n = len(values)
        # Six-hour means now and three days ago, wide enough that the daily dew
        # wobble averages out; the same rule the display uses.
        now_mean = _mean(values, n - 6, n)
        then_mean = _mean(values, n - 75, n - 69)
        self.trend = (
            round((now_mean - then_mean) / 3, 2)
            if now_mean is not None and then_mean is not None
            else None
        )
        self._recompute_forecast()
        self._signal()

    def _recompute_forecast(self) -> None:
        current = self.moisture
        if (
            self.trend is None
            or current is None
            or self.trend > FALLING_PER_DAY
            or current <= self.floor
        ):
            self.forecast = None
            return
        days = (current - self.floor) / -self.trend
        self.forecast = dt_util.utcnow() + timedelta(days=days)

    # ---------- actions ----------

    async def async_mark_watered(self, at: datetime | None = None) -> None:
        """The button: stamp now and tell the detector this water is accounted for."""
        at = at or dt_util.utcnow()
        self._detector.mark_watered(at)
        self._stamp(at, "button", None)

    async def async_set_band(
        self, floor: float | None = None, ceiling: float | None = None
    ) -> None:
        if floor is not None:
            self.floor = floor
        if ceiling is not None:
            self.ceiling = ceiling
        self._recompute_forecast()
        self._save()
        self._signal()

    def _stamp(self, at: datetime, by: str, rise: float | None) -> None:
        self.last_watered = at
        self.last_watered_by = by
        self._save()
        self.hass.bus.async_fire(
            EVENT_WATERED,
            {
                "entry_id": self.entry.entry_id,
                "name": self.name,
                "at": at.isoformat(),
                "by": by,
                "rise": rise,
            },
        )
        _LOGGER.debug("%s watered at %s (%s, rise %s)", self.name, at, by, rise)
        self._signal()

    # ---------- derived ----------

    @staticmethod
    def _num(state: State | None) -> float | None:
        if state is None or state.state in _UNUSABLE:
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None

    def reading(self, key: str) -> tuple[float | None, int | None, str | None]:
        """(value, seconds since the sensor last reported, unit) for one reading."""
        entity_id = self.sources.get(key)
        state = self.hass.states.get(entity_id) if entity_id else None
        value = self._num(state)
        if state is None or value is None:
            return None, None, None
        reported = getattr(state, "last_reported", None) or state.last_updated
        age = max(0, int((dt_util.utcnow() - reported).total_seconds()))
        return value, age, state.attributes.get("unit_of_measurement")

    @property
    def moisture(self) -> float | None:
        return self.reading(CONF_MOISTURE)[0]

    @property
    def status(self) -> str:
        value, age, _ = self.reading(CONF_MOISTURE)
        if value is None or age is None or age > STALE_AFTER.total_seconds():
            return STATUS_STALE
        if value <= 0:
            return STATUS_CHECK_PROBE  # a working probe in any soil reads above zero
        if value < self.floor:
            return STATUS_DRY
        if self.forecast is not None and self.forecast - dt_util.utcnow() < timedelta(
            days=SOON_DAYS
        ):
            return STATUS_WATER_SOON
        return STATUS_OK

    @property
    def pending(self) -> dict[str, Any] | None:
        """A watering the detector has seen but not yet confirmed."""
        seen = self._detector.pending
        confirms = self._detector.confirms_at
        if seen is None or confirms is None:
            return None
        return {
            "since": seen.at.isoformat(),
            "rise": seen.rise,
            "confirms_at": confirms.isoformat(),
        }

    @property
    def needs_water(self) -> bool:
        value = self.moisture
        return value is not None and 0 < value < self.floor

    @property
    def sensor_label(self) -> str:
        """The sensor device's own name ("Plant Sensor 6C31"), not the rename."""
        if not self.device_id:
            return ""
        device = dr.async_get(self.hass).async_get(self.device_id)
        return (device.name or "") if device else ""

    def snapshot(self) -> dict[str, Any]:
        """Everything a card or the display needs, in one dict."""
        readings: dict[str, Any] = {}
        for key in READINGS:
            value, age, unit = self.reading(key)
            readings[key] = {
                "entity_id": self.sources.get(key),
                "value": value,
                "age": age,
                "unit": unit,
            }
        return {
            "entry_id": self.entry.entry_id,
            "name": self.name,
            "species": self.species,
            "profile": self.profile,
            "icon": self.icon,
            "icon_image": self.icon_image,
            "icon_display": self.icon_display,
            "device_id": self.device_id,
            "sensor": self.sensor_label,
            "readings": readings,
            "floor": self.floor,
            "ceiling": self.ceiling,
            "last_watered": self.last_watered.isoformat()
            if self.last_watered
            else None,
            "last_watered_by": self.last_watered_by,
            "watering_pending": self.pending,
            "status": self.status,
            "needs_water": self.needs_water,
            "trend": self.trend,
            "forecast": self.forecast.isoformat() if self.forecast else None,
        }

    async def async_history(
        self, hours: int = HISTORY_HOURS
    ) -> tuple[datetime, list[float | None]]:
        moisture = self.sources.get(CONF_MOISTURE)
        start, series = await async_hourly_means(
            self.hass, [moisture] if moisture else [], hours
        )
        return start, series.get(moisture, []) if moisture else []

    # ---------- plumbing ----------

    def _record(self) -> dict[str, Any]:
        return {
            "floor": self.floor,
            "ceiling": self.ceiling,
            "last_watered": self.last_watered.isoformat()
            if self.last_watered
            else None,
            "last_watered_by": self.last_watered_by,
        }

    def _save(self) -> None:
        self._store.async_delay_save(self._record, 2)

    def _signal(self) -> None:
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATED}_{self.entry.entry_id}")

    def add_listener(self, target: Callable[[], None]) -> CALLBACK_TYPE:
        return async_dispatcher_connect(
            self.hass, f"{SIGNAL_UPDATED}_{self.entry.entry_id}", target
        )
