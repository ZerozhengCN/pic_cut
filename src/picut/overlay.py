"""Render a debug overlay: original image with bbox + label drawn on it."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .detect import Detection

_LABEL_COLORS = {
    "talent_node": (255, 196, 0),
    "ui_frame": (0, 200, 255),
}
_DEFAULT_COLOR = (255, 0, 128)


def _color(label: str) -> tuple[int, int, int]:
    return _LABEL_COLORS.get(label, _DEFAULT_COLOR)


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_overlay(
    img: Image.Image,
    detections: list[Detection],
    out_path: Path,
) -> None:
    canvas = img.convert("RGBA").copy()
    draw = ImageDraw.Draw(canvas, "RGBA")
    font = _font(max(14, img.width // 100))

    for idx, det in enumerate(detections, start=1):
        x0, y0, x1, y1 = det.bbox_pixels(img.width, img.height)
        color = _color(det.label)
        draw.rectangle((x0, y0, x1, y1), outline=color + (255,), width=3)
        tag = f"{idx:02d} {det.label} {det.confidence:.2f}"
        tw, th = draw.textbbox((0, 0), tag, font=font)[2:]
        bg_y0 = max(0, y0 - th - 4)
        draw.rectangle((x0, bg_y0, x0 + tw + 8, bg_y0 + th + 4), fill=color + (200,))
        draw.text((x0 + 4, bg_y0 + 2), tag, fill=(0, 0, 0, 255), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG")
