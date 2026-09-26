# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Custom plant icons: an uploaded image turned into a one-colour mask.

The mask is what gets tinted: the card paints it in the status colour, the
FireLabs display draws it as an A8 image like the built-in marks.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageChops, ImageOps, UnidentifiedImageError

MASK_SIZE = 128  # stored, and what the card draws
DISPLAY_SIZE = 34  # the display's notch icon
MARGIN = 0.06
MAX_SOURCE_PX = 4096


class IconError(ValueError):
    """The upload can't be used; the value is a config-flow error key."""


def _range(band: Image.Image) -> tuple[int, int]:
    """Min and max of a single-band image (getextrema is typed for every mode)."""
    lo, hi = band.getextrema()
    return int(lo), int(hi)  # type: ignore[arg-type]


def _mask(img: Image.Image) -> Image.Image:
    """The drawing as white-on-black: alpha if the image has any, else contrast."""
    rgba = ImageOps.exif_transpose(img).convert("RGBA")
    alpha = rgba.getchannel("A")
    if _range(alpha)[0] < 200:  # real transparency: the shape is whatever is opaque
        return alpha
    # Solid background: the drawing is whatever differs from the border colour,
    # so dark-on-light and light-on-dark both work.
    grey = rgba.convert("L")
    w, h = grey.size
    border = [grey.getpixel((x, 0)) for x in range(w)] + [
        grey.getpixel((x, h - 1)) for x in range(w)
    ]
    border.sort()
    bg = border[len(border) // 2]
    diff = ImageChops.difference(grey, Image.new("L", grey.size, bg))
    top = _range(diff)[1]
    if top < 24:
        raise IconError("icon_empty")
    return diff.point(lambda v: min(255, v * 255 // top))


def make_mask(data: bytes) -> bytes:
    """PNG bytes of the square MASK_SIZE mask for an uploaded image."""
    try:
        img = Image.open(io.BytesIO(data))
        if max(img.size) > MAX_SOURCE_PX:
            raise IconError("icon_too_big")
        mask = _mask(img)
    except (UnidentifiedImageError, OSError) as err:
        raise IconError("icon_unreadable") from err
    box = mask.point(lambda v: 255 if v > 24 else 0).getbbox()
    if not box:
        raise IconError("icon_empty")
    mask = mask.crop(box)
    side = int(max(mask.size) * (1 + 2 * MARGIN))
    square = Image.new("L", (side, side), 0)
    square.paste(mask, ((side - mask.width) // 2, (side - mask.height) // 2))
    out = io.BytesIO()
    square.resize((MASK_SIZE, MASK_SIZE), Image.Resampling.LANCZOS).save(
        out, "PNG", optimize=True
    )
    return out.getvalue()


def mask_from_file(path: Path) -> str:
    """Base64 mask PNG for an uploaded file (runs in the executor)."""
    return base64.b64encode(make_mask(path.read_bytes())).decode()


def display_mask(mask_b64: str) -> str:
    """Base64 of the raw DISPLAY_SIZE x DISPLAY_SIZE A8 bytes the display draws."""
    img = Image.open(io.BytesIO(base64.b64decode(mask_b64))).convert("L")
    small = img.resize((DISPLAY_SIZE, DISPLAY_SIZE), Image.Resampling.LANCZOS)
    return base64.b64encode(small.tobytes()).decode()
