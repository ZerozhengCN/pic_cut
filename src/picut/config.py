"""Run configuration shared across pipeline stages."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DETECT_MODEL_DEFAULT = "gemini-3.1-pro-preview"
EXTRACT_MODEL_DEFAULT = "gemini-3.1-flash-image-preview"

OUTPUT_SIZE = 1024

DETECT_TEMPERATURE = 1.0


@dataclass
class RunConfig:
    input_dir: Path
    output_dir: Path
    detect_model: str = DETECT_MODEL_DEFAULT
    extract_model: str = EXTRACT_MODEL_DEFAULT
    categories: list[str] | None = None
    padding: float = 0.08
    matting: str = "auto"
    concurrency: int = 4
    resume: bool = False
    dry_run: bool = False
    max_icons_per_shot: int = 100
    output_size: int = OUTPUT_SIZE
    verbose: bool = False
    extra_categories: list[str] = field(default_factory=list)
    redetect: bool = False

    def screenshot_out_dir(self, screenshot_path: Path) -> Path:
        return self.output_dir / screenshot_path.stem
