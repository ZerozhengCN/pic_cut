"""Call nano-banana (Gemini 3.1 Flash Image Preview) to re-render a clean icon.

The model does NOT support transparent output, so we ask for a solid
background (white by default, magenta as a chroma-key fallback) and matte
locally in matte.py.
"""
from __future__ import annotations

import io

from google import genai
from google.genai import types
from PIL import Image

from .retry import retry_api

WHITE_PROMPT = """\
You are given a cropped region from a game UI screenshot.

Re-render ONLY the {label} icon shown in the input, isolated and centered
on a pure white (#FFFFFF) background. Preserve the icon's exact colors,
shapes, ornamental detail, and proportions. Do NOT add new elements, text,
shadows, or decoration. Do NOT change the art style. Output a single 1:1
square image at 1024x1024 with the icon occupying roughly 80% of the frame,
centered with comfortable padding.

If the input contains multiple icons or partial content, pick the most
visually dominant complete icon and ignore the rest.
"""

MAGENTA_PROMPT = """\
You are given a cropped region from a game UI screenshot.

Re-render ONLY the {label} icon shown in the input, isolated and centered
on a pure magenta (#FF00FF) background. The background must be uniform pure
magenta with no shading or gradient, used purely as a chroma-key color.
Preserve the icon's exact colors, shapes, ornamental detail, and proportions.
Do NOT add new elements, text, shadows, or decoration. Output a 1:1 square
image at 1024x1024 with the icon occupying roughly 80% of the frame.

If the icon itself contains a magenta color, replace it with the closest
non-magenta color so the chroma-key remains valid.
"""


def _image_config(size: str = "1K", aspect: str = "1:1"):
    """Build the image config in a way that tolerates SDK field-name drift."""
    image_cfg_cls = getattr(types, "ImageConfig", None)
    if image_cfg_cls is None:
        return None
    try:
        return image_cfg_cls(image_size=size, aspect_ratio=aspect)
    except (TypeError, ValueError):
        try:
            return image_cfg_cls(aspect_ratio=aspect)
        except (TypeError, ValueError):
            return None


def _build_config():
    image_cfg = _image_config()
    kwargs: dict = {"response_modalities": ["IMAGE"]}
    if image_cfg is not None:
        kwargs["image_config"] = image_cfg
    return types.GenerateContentConfig(**kwargs)


def _decode_image(resp) -> Image.Image:
    candidates = getattr(resp, "candidates", None) or []
    parts = []
    if candidates:
        content = getattr(candidates[0], "content", None)
        if content is not None:
            parts = getattr(content, "parts", []) or []
    if not parts:
        parts = getattr(resp, "parts", []) or []

    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline is not None and getattr(inline, "data", None):
            return Image.open(io.BytesIO(inline.data)).convert("RGB")
    raise RuntimeError("nano-banana response contained no image data")


@retry_api
def render(
    client: genai.Client,
    model: str,
    crop: Image.Image,
    label: str,
    background: str = "white",
) -> Image.Image:
    if background == "magenta":
        prompt = MAGENTA_PROMPT.format(label=label)
    else:
        prompt = WHITE_PROMPT.format(label=label)

    resp = client.models.generate_content(
        model=model,
        contents=[prompt, crop],
        config=_build_config(),
    )
    return _decode_image(resp)
