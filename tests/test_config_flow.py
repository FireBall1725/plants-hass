# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Adding a plant finds its readings on the device."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from PIL import Image, ImageDraw
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import SENSORS


async def test_pick_device_finds_all_readings(
    hass: HomeAssistant, sensor_device: str
) -> None:
    result = await hass.config_entries.flow.async_init(
        "plants", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device_id": sensor_device,
            "profile": "succulent",
            "species": "Crassula ovata",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jade"  # the user's name for the device
    options = result["options"]
    for key, (entity_id, _, _) in SENSORS.items():
        assert options[key] == entity_id
    assert options["threshold"] == 6
    assert options["icon"] == "succulent"  # picked from the succulent profile


async def test_same_device_twice_aborts(
    hass: HomeAssistant, sensor_device: str
) -> None:
    for expected in (FlowResultType.CREATE_ENTRY, FlowResultType.ABORT):
        result = await hass.config_entries.flow.async_init(
            "plants", context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_id": sensor_device, "profile": "custom"}
        )
        assert result["type"] is expected


@contextmanager
def uploaded(path: Path) -> Iterator[Path]:
    yield path


async def test_upload_sets_a_custom_icon_and_keeps_it(
    hass: HomeAssistant, jade: MockConfigEntry, tmp_path: Path
) -> None:
    image = tmp_path / "leaf.png"
    img = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((10, 20, 70, 60), fill=(0, 120, 0, 255))
    img.save(image)
    base = {"profile": "succulent", "threshold": 6}

    result = await hass.config_entries.options.async_init(jade.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**base, "icon": "custom"}
    )
    assert result["errors"] == {"base": "icon_file_required"}

    with patch(
        "custom_components.plants.config_flow.process_uploaded_file",
        lambda _hass, _id: uploaded(image),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                **base,
                "icon": "succulent",
                "icon_file": "8f5c8e3a-2f7e-4c52-9a55-3d1f0b6f2e11",
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert jade.options["icon"] == "custom"
    mask = jade.options["icon_mask"]
    assert "icon_file" not in jade.options

    # Saving again without a new upload keeps the mask.
    result = await hass.config_entries.options.async_init(jade.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**base, "icon": "custom"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert jade.options["icon_mask"] == mask
    await hass.async_block_till_done()
    plant = jade.runtime_data
    assert plant.icon == "custom"
    assert plant.icon_image.startswith("data:image/png;base64,")
    assert plant.icon_display
