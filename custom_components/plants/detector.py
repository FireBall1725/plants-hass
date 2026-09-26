# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Watering detection from a soil moisture stream.

Plain Python on purpose: no Home Assistant imports, so the rules are tested
directly against real curves.

A watering is a rise of at least `threshold` points in the smoothed reading,
measured from the lowest point of the last twelve hours, that is still there
six hours later. The morning dew fails both tests: it adds two or three points
to a dry pot and is gone by noon. The watering is stamped at the moment the
rise started, not when it was confirmed.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from .const import HOLD, MANUAL_GRACE, RISE_WINDOW, SMOOTHING


@dataclass(frozen=True)
class Watering:
    """A confirmed watering."""

    at: datetime  # when the rise started
    rise: float  # points added, smoothed


@dataclass
class _Candidate:
    baseline: float
    started: datetime
    crossed: datetime


class WateringDetector:
    """Feed it readings in time order; it returns a Watering when one is confirmed."""

    def __init__(
        self,
        threshold: float,
        *,
        smoothing: timedelta = SMOOTHING,
        window: timedelta = RISE_WINDOW,
        hold: timedelta = HOLD,
    ) -> None:
        self.threshold = threshold
        self._smoothing = smoothing
        self._window = window
        self._hold = hold
        self._raw: deque[tuple[datetime, float]] = deque()
        self._smoothed: deque[tuple[datetime, float]] = deque()
        self._candidate: _Candidate | None = None
        # Lows from before the last watering don't count as a baseline.
        self._floor_after: datetime | None = None
        self._manual_at: datetime | None = None
        self._last_ts: datetime | None = None

    @property
    def pending(self) -> Watering | None:
        """A rise seen but not yet held long enough: when it started, how big so far."""
        cand = self._candidate
        if cand is None or not self._smoothed:
            return None
        return Watering(
            at=cand.started, rise=round(self._smoothed[-1][1] - cand.baseline, 1)
        )

    @property
    def confirms_at(self) -> datetime | None:
        """When the pending rise will count, if it holds."""
        return self._candidate.crossed + self._hold if self._candidate else None

    def mark_watered(self, at: datetime) -> None:
        """The button was pressed: that water is accounted for."""
        self._manual_at = at
        self._floor_after = at
        self._candidate = None

    def feed(self, ts: datetime, value: float) -> Watering | None:
        """Add one reading; out-of-order readings are ignored."""
        if self._last_ts is not None and ts <= self._last_ts:
            return None
        self._last_ts = ts

        self._raw.append((ts, value))
        while self._raw and ts - self._raw[0][0] > self._smoothing:
            self._raw.popleft()
        smoothed = sum(v for _, v in self._raw) / len(self._raw)

        self._smoothed.append((ts, smoothed))
        while self._smoothed and ts - self._smoothed[0][0] > self._window:
            self._smoothed.popleft()

        cand = self._candidate
        if cand is None:
            return self._maybe_start(ts, smoothed)
        if smoothed - cand.baseline < self.threshold:
            self._candidate = None  # it drained away: dew, a splash, a probe knock
            return self._maybe_start(ts, smoothed)
        if ts - cand.crossed < self._hold:
            return None

        self._candidate = None
        self._floor_after = ts
        if (
            self._manual_at is not None
            and cand.started - self._manual_at < MANUAL_GRACE
        ):
            return None  # the button already stamped this one
        return Watering(at=cand.started, rise=round(smoothed - cand.baseline, 1))

    def _maybe_start(self, ts: datetime, smoothed: float) -> Watering | None:
        window = [
            (t, v)
            for t, v in self._smoothed
            if self._floor_after is None or t >= self._floor_after
        ]
        if not window:
            return None
        low_ts, low = min(window, key=lambda tv: tv[1])
        if smoothed - low < self.threshold:
            return None
        # The water went in after the last reading still in the lower half of the
        # rise. (Not "near the low": one early dip under a pot that wobbles by a
        # point would pin the start hours too early.)
        started = low_ts
        for t, v in window:
            if t >= low_ts and v < low + self.threshold / 2:
                started = t
        self._candidate = _Candidate(baseline=low, started=started, crossed=ts)
        return None
