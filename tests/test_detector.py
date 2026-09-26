# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""The watering detector against a real week of curves."""

from __future__ import annotations

from datetime import timedelta

from custom_components.plants.detector import WateringDetector

from .curves import BASIL, GINGER, JADE, WATERED_HOUR, at


def run(series: list[float], threshold: float) -> list:
    detector = WateringDetector(threshold)
    found = []
    for hour, value in enumerate(series):
        watering = detector.feed(at(hour), value)
        if watering:
            found.append((hour, watering))
    return found


def test_jade_monday_watering_found_once() -> None:
    found = run(JADE, threshold=6)
    assert len(found) == 1
    confirmed_hour, watering = found[0]
    # Stamped when the rise started (hourly data: within an hour of 22:07Z),
    # confirmed six hours later.
    assert abs(watering.at - at(WATERED_HOUR)) <= timedelta(hours=1)
    assert confirmed_hour == WATERED_HOUR + 6
    assert watering.rise > 12


def test_jade_morning_dew_is_not_water() -> None:
    # Only the Monday watering: the 09:00 bump on the last morning (hours 158-161)
    # and the earlier ones must not show up.
    found = run(JADE, threshold=6)
    assert all(hour < 150 for hour, _ in found)


def test_ginger_probe_recovery_and_watering() -> None:
    found = run(GINGER, threshold=10)
    assert len(found) == 1
    assert abs(found[0][1].at - at(WATERED_HOUR)) <= timedelta(hours=1)
    assert found[0][1].rise > 40


def test_basil_flat_all_week() -> None:
    assert run(BASIL, threshold=10) == []


def test_rise_that_drains_away_is_dropped() -> None:
    detector = WateringDetector(10)
    base = [5.0] * 12 + [20.0] * 3 + [5.0] * 12  # a splash that is gone in 3 hours
    assert [w for h, v in enumerate(base) if (w := detector.feed(at(h), v))] == []


def test_button_press_absorbs_the_same_water() -> None:
    detector = WateringDetector(10)
    for hour in range(12):
        detector.feed(at(hour), 5.0)
    detector.mark_watered(at(12))
    found = [w for h in range(12, 30) if (w := detector.feed(at(h), 40.0))]
    assert found == []


def test_out_of_order_readings_ignored() -> None:
    detector = WateringDetector(10)
    detector.feed(at(5), 5.0)
    assert detector.feed(at(4), 50.0) is None


def test_pending_rise_is_visible_until_confirmed() -> None:
    detector = WateringDetector(10)
    for hour in range(12):
        detector.feed(at(hour), 5.0)
    assert detector.pending is None
    detector.feed(at(12), 30.0)
    assert detector.pending is not None
    assert detector.pending.rise == 25.0
    assert detector.confirms_at == at(12) + timedelta(hours=6)
    for hour in range(13, 19):
        detector.feed(at(hour), 30.0)
    assert detector.pending is None  # confirmed and handed back as a Watering


def test_start_is_the_jump_not_an_early_dip() -> None:
    # Basil on 2026-09-25: one 3 at 08:00 local, then wobbling 4-5 until the
    # watering took it to 40 at about 17:15.
    detector = WateringDetector(10)
    readings = [(0.0, 4.0), (1.0, 3.0), (1.5, 4.0)]
    readings += [
        (2 + i / 4, 4.0 if i % 2 else 5.0) for i in range(36)
    ]  # 11:00 to 20:00
    readings += [(11.25, 40.0), (11.5, 31.0), (12.0, 30.0)]
    for hour, value in readings:
        detector.feed(at(hour), value)
    assert detector.pending is not None
    assert at(10.5) <= detector.pending.at < at(11.25)
