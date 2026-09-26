# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Uploaded images become one-colour marks."""

from __future__ import annotations

import base64
import io

import pytest
from custom_components.plants.icon import (
    DISPLAY_SIZE,
    MASK_SIZE,
    IconError,
    display_mask,
    make_mask,
)
from PIL import Image, ImageDraw


def png(img: Image.Image, fmt: str = "PNG") -> bytes:
    out = io.BytesIO()
    img.save(out, fmt)
    return out.getvalue()


def leaf(mode: str, bg: tuple[int, ...], fg: tuple[int, ...]) -> Image.Image:
    img = Image.new(mode, (300, 200), bg)
    ImageDraw.Draw(img).ellipse((120, 40, 200, 160), fill=fg)
    return img


def coverage(mask_png: bytes) -> float:
    img = Image.open(io.BytesIO(mask_png))
    assert img.size == (MASK_SIZE, MASK_SIZE)
    return sum(1 for v in img.getdata() if v > 128) / (MASK_SIZE * MASK_SIZE)


def test_transparent_png_uses_its_alpha() -> None:
    mask = make_mask(png(leaf("RGBA", (0, 0, 0, 0), (40, 160, 60, 255))))
    # Trimmed to the shape and squared: the ellipse fills most of the frame.
    assert 0.4 < coverage(mask) < 0.8


@pytest.mark.parametrize(
    ("bg", "fg"), [((255, 255, 255), (20, 20, 20)), ((10, 10, 10), (240, 240, 240))]
)
def test_plain_background_either_way_round(
    bg: tuple[int, ...], fg: tuple[int, ...]
) -> None:
    mask = make_mask(png(leaf("RGB", bg, fg), "JPEG"))
    assert 0.4 < coverage(mask) < 0.8


def test_blank_image_is_refused() -> None:
    with pytest.raises(IconError, match="icon_empty"):
        make_mask(png(Image.new("RGB", (64, 64), (255, 255, 255))))


def test_not_an_image_is_refused() -> None:
    with pytest.raises(IconError, match="icon_unreadable"):
        make_mask(b"not an image")


def test_display_mask_is_raw_a8() -> None:
    mask = base64.b64encode(
        make_mask(png(leaf("RGBA", (0, 0, 0, 0), (0, 0, 0, 255))))
    ).decode()
    raw = base64.b64decode(display_mask(mask))
    assert len(raw) == DISPLAY_SIZE * DISPLAY_SIZE
    assert max(raw) > 200
