# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Reading the recorder: hourly curves and recent raw readings."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from .const import HISTORY_TTL

# {(entity ids, hours): (fetched monotonic, start, {entity_id: series})}
_cache: dict[tuple[tuple[str, ...], int], tuple[float, datetime, dict[str, list]]] = {}


def _recorder_ready(hass: HomeAssistant) -> bool:
    return "recorder" in hass.config.components


async def async_hourly_means(
    hass: HomeAssistant, entity_ids: list[str], hours: int
) -> tuple[datetime, dict[str, list[float | None]]]:
    """Hourly mean per entity for the last `hours` complete hours.

    Long-term statistics rather than raw history: one averaged row per hour, and
    they outlive the recorder's purge window. Trailing empty hours (the one in
    progress) are dropped so a curve ends on real data.
    """
    start = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(
        hours=hours
    )
    key = (tuple(sorted(entity_ids)), hours)
    cached = _cache.get(key)
    if cached and cached[1] == start and time.monotonic() - cached[0] < HISTORY_TTL:
        return start, cached[2]

    result: dict[str, list[float | None]] = {eid: [] for eid in entity_ids}
    if entity_ids and _recorder_ready(hass):
        from homeassistant.components.recorder import get_instance  # noqa: PLC0415
        from homeassistant.components.recorder.statistics import (  # noqa: PLC0415
            statistics_during_period,
        )

        stats = await get_instance(hass).async_add_executor_job(
            statistics_during_period,
            hass,
            start,
            None,
            set(entity_ids),
            "hour",
            None,
            {"mean"},
        )
        start_ts = start.timestamp()
        for entity_id in entity_ids:
            series: list[float | None] = [None] * hours
            for row in stats.get(entity_id, []):
                row_start = row.get("start")
                if isinstance(row_start, datetime):
                    row_start = row_start.timestamp()
                mean = row.get("mean")
                if row_start is None or mean is None:
                    continue
                i = int((row_start - start_ts) // 3600)
                if 0 <= i < hours:
                    series[i] = round(mean, 1)
            while series and series[-1] is None:
                series.pop()
            result[entity_id] = series
    _cache[key] = (time.monotonic(), start, result)
    return start, result


async def async_recent_states(
    hass: HomeAssistant, entity_id: str, since: timedelta
) -> list[State]:
    """Raw state changes of one entity, oldest first, for replaying the detector."""
    if not _recorder_ready(hass):
        return []
    from homeassistant.components.recorder import get_instance, history  # noqa: PLC0415

    start = dt_util.utcnow() - since
    changes = await get_instance(hass).async_add_executor_job(
        lambda: history.state_changes_during_period(
            hass, start, None, entity_id, no_attributes=True
        )
    )
    return list(changes.get(entity_id, []))
