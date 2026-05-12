"""Crop helpers: bbox + padding, with image-bound clamping."""
from __future__ import annotations

from PIL import Image


def crop_with_padding(
    img: Image.Image,
    bbox_pixels: tuple[int, int, int, int],
    padding: float,
) -> Image.Image:
    x0, y0, x1, y1 = bbox_pixels
    w, h = x1 - x0, y1 - y0
    pad_x = int(w * padding)
    pad_y = int(h * padding)
    x0p = max(0, x0 - pad_x)
    y0p = max(0, y0 - pad_y)
    x1p = min(img.width, x1 + pad_x)
    y1p = min(img.height, y1 + pad_y)
    return img.crop((x0p, y0p, x1p, y1p))


def bbox_hash(bbox_pixels: tuple[int, int, int, int]) -> str:
    return "_".join(str(v) for v in bbox_pixels)
