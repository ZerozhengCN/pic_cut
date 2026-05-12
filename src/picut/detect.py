"""Gemini vision detection: bounding boxes for icons/UI elements."""
from __future__ import annotations

import json
from dataclasses import dataclass

from google import genai
from google.genai import types
from PIL import Image

from .config import DETECT_TEMPERATURE
from .retry import retry_api

DETECTION_PROMPT = """\
You are analyzing a screenshot from a Chinese game UI. Detect every visually
distinct UI icon or badge that looks like a reusable graphical asset.

Two categories to label:

  1. "talent_node"  - circular icons inside a talent / skill tree
                      (typically a round symbol with a decorative ring,
                      sometimes glowing or locked).
  2. "ui_frame"     - decorative borders, ornamental buttons, seals,
                      badges, crests, banners, ribbons, or other framed
                      graphical UI elements.

Ignore:
  - plain text labels and Chinese character glyphs
  - solid color rectangles with no decoration
  - the game world / background scenery
  - cursors, thin connecting lines, or progress bars

Return ONLY valid JSON of this exact shape, no other text, no markdown:

{
  "items": [
    {
      "label": "talent_node" | "ui_frame",
      "box_2d": [ymin, xmin, ymax, xmax],
      "confidence": 0.0,
      "shape_hint": "circle" | "rect" | "shield" | "other",
      "description": "short description, max 8 words"
    }
  ]
}

Coordinates are normalized to 0-1000. Be exhaustive: include every icon
you can clearly delineate, even if there are 50+.
"""


@dataclass
class Detection:
    label: str
    box_2d: tuple[int, int, int, int]
    confidence: float
    shape_hint: str
    description: str

    def bbox_pixels(self, img_w: int, img_h: int) -> tuple[int, int, int, int]:
        ymin, xmin, ymax, xmax = self.box_2d
        x0 = max(0, min(img_w, int(xmin / 1000 * img_w)))
        y0 = max(0, min(img_h, int(ymin / 1000 * img_h)))
        x1 = max(0, min(img_w, int(xmax / 1000 * img_w)))
        y1 = max(0, min(img_h, int(ymax / 1000 * img_h)))
        if x1 <= x0:
            x1 = min(img_w, x0 + 1)
        if y1 <= y0:
            y1 = min(img_h, y0 + 1)
        return x0, y0, x1, y1

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "box_2d": list(self.box_2d),
            "confidence": self.confidence,
            "shape_hint": self.shape_hint,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Detection":
        return cls(
            label=d["label"],
            box_2d=tuple(d["box_2d"]),
            confidence=d.get("confidence", 1.0),
            shape_hint=d.get("shape_hint", ""),
            description=d.get("description", ""),
        )


@retry_api
def _call_model(client: genai.Client, model: str, img: Image.Image, temperature: float) -> str:
    resp = client.models.generate_content(
        model=model,
        contents=[DETECTION_PROMPT, img],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=temperature,
        ),
    )
    return resp.text or ""


def _parse(raw: str) -> list[Detection]:
    data = json.loads(raw)
    items = data.get("items", []) if isinstance(data, dict) else data
    out: list[Detection] = []
    for it in items:
        try:
            box = it["box_2d"]
            if len(box) != 4:
                continue
            out.append(
                Detection(
                    label=str(it.get("label", "ui_frame")),
                    box_2d=(int(box[0]), int(box[1]), int(box[2]), int(box[3])),
                    confidence=float(it.get("confidence", 0.0)),
                    shape_hint=str(it.get("shape_hint", "other")),
                    description=str(it.get("description", "")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def detect(
    client: genai.Client,
    img: Image.Image,
    model: str,
    temperature: float = DETECT_TEMPERATURE,
) -> list[Detection]:
    raw = _call_model(client, model, img, temperature)
    try:
        items = _parse(raw)
    except json.JSONDecodeError:
        raw = _call_model(client, model, img, temperature)
        items = _parse(raw)
    return items
