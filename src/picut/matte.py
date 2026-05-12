"""Local alpha matting: rembg primary, magenta chroma-key fallback."""
from __future__ import annotations

import numpy as np
from PIL import Image

_REMBG_SESSION = None


def _session():
    global _REMBG_SESSION
    if _REMBG_SESSION is None:
        from rembg import new_session

        _REMBG_SESSION = new_session("u2net")
    return _REMBG_SESSION


def matte_rembg(img_rgb: Image.Image) -> Image.Image:
    from rembg import remove

    rgba = remove(img_rgb, session=_session())
    if rgba.mode != "RGBA":
        rgba = rgba.convert("RGBA")
    return rgba


def alpha_coverage(rgba: Image.Image) -> float:
    a = np.asarray(rgba.split()[-1], dtype=np.uint8)
    return float((a > 200).mean())


def chroma_key_magenta(img_rgb: Image.Image, tolerance: int = 35) -> Image.Image:
    arr = np.asarray(img_rgb.convert("RGB"), dtype=np.int16)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    is_magenta = (r > 255 - tolerance) & (g < tolerance) & (b > 255 - tolerance)
    alpha = np.where(is_magenta, 0, 255).astype(np.uint8)

    rgb = arr.astype(np.uint8)
    edge = is_magenta & ~np.roll(is_magenta, 1, axis=0) & ~np.roll(is_magenta, -1, axis=0)
    rgb[edge] = (rgb[np.roll(edge, 1, axis=0)] + rgb[np.roll(edge, -1, axis=0)]) // 2

    rgba = np.dstack([rgb, alpha])
    return Image.fromarray(rgba, mode="RGBA")


def center_pad_square(rgba: Image.Image, size: int) -> Image.Image:
    w, h = rgba.size
    if (w, h) == (size, size):
        return rgba

    scale = min(size / w, size / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    resized = rgba.resize((nw, nh), Image.LANCZOS)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(resized, ((size - nw) // 2, (size - nh) // 2), resized)
    return canvas
