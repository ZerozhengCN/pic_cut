"""Per-screenshot orchestration: detect -> crop -> extract -> matte -> save."""
from __future__ import annotations

import json
import time
import traceback
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from google import genai
from PIL import Image

from . import extract, matte
from .config import RunConfig
from .crop import bbox_hash, crop_with_padding
from .detect import Detection, detect
from .log import RunLog, completed_keys, console
from .overlay import render_overlay

DEFAULT_CATEGORIES = ("talent_node", "ui_frame")
ALPHA_THRESHOLD_FAILURE = 0.05


def _save_detection_json(items: list[Detection], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"items": [it.to_dict() for it in items]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_detection_json(path: Path) -> list[Detection] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [Detection.from_dict(it) for it in payload["items"]]
    except Exception:
        return None


def _matte(rendered: Image.Image, strategy: str) -> tuple[Image.Image, str]:
    """Returns (rgba, used_strategy)."""
    if strategy == "magenta":
        return matte.chroma_key_magenta(rendered), "magenta"
    if strategy == "rembg":
        return matte.matte_rembg(rendered), "rembg"

    rgba = matte.matte_rembg(rendered)
    if matte.alpha_coverage(rgba) < ALPHA_THRESHOLD_FAILURE:
        return rgba, "rembg_lowcov"
    return rgba, "rembg"


def _icon_filename(label: str, idx: int) -> str:
    return f"{label}_{idx:02d}.png"


def process_screenshot(
    client: genai.Client,
    screenshot_path: Path,
    cfg: RunConfig,
    run_log: RunLog,
) -> dict:
    out_dir = cfg.screenshot_out_dir(screenshot_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(screenshot_path).convert("RGB")

    detection_json = out_dir / "_detection.json"
    cached = None if cfg.redetect else _load_detection_json(detection_json)
    if cached is not None:
        items = cached
        console.print(
            f"[bold]{screenshot_path.name}[/bold] {img.width}x{img.height} "
            f"→ [dim]detection cached ({len(items)} items)[/dim]"
        )
    else:
        console.print(f"[bold]{screenshot_path.name}[/bold] {img.width}x{img.height} → detect...")
        try:
            items = detect(client, img, cfg.detect_model)
        except Exception as e:
            run_log.write(
                screenshot=screenshot_path.name, stage="detect", status="error", error=str(e)
            )
            console.print(f"  [red]detect failed:[/red] {e}")
            return {"detected": 0, "extracted": 0, "failed": 0}

        if cfg.redetect and detection_json.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            detection_json.rename(out_dir / f"_detection_{ts}.json")
            overlay = out_dir / "_overlay.png"
            if overlay.exists():
                overlay.rename(out_dir / f"_overlay_{ts}.png")

        _save_detection_json(items, detection_json)
        render_overlay(img, items, out_dir / "_overlay.png")
        console.print(f"  detected {len(items)} items, overlay → {out_dir.name}/_overlay.png")

    if cfg.dry_run:
        return {"detected": len(items), "extracted": 0, "failed": 0}

    cats = set(cfg.categories) if cfg.categories else set(DEFAULT_CATEGORIES)
    cats |= set(cfg.extra_categories)

    done = completed_keys(cfg.output_dir / "_run.jsonl") if cfg.resume else set()

    counters: dict[str, int] = defaultdict(int)
    extracted = 0
    failed = 0

    for det in items[: cfg.max_icons_per_shot]:
        if det.label not in cats:
            continue

        bbox = det.bbox_pixels(img.width, img.height)
        bhash = bbox_hash(bbox)
        key = f"{screenshot_path.name}|{det.label}|{bhash}"

        counters[det.label] += 1
        idx = counters[det.label]
        out_path = out_dir / _icon_filename(det.label, idx)

        if cfg.resume and key in done and out_path.exists():
            console.print(f"  [dim]skip {out_path.name} (resume)[/dim]")
            continue

        crop = crop_with_padding(img, bbox, cfg.padding)

        t0 = time.time()
        try:
            rendered = extract.render(client, cfg.extract_model, crop, det.label, "white")
            rgba, used = _matte(rendered, cfg.matting)

            if used == "rembg_lowcov" and cfg.matting == "auto":
                rendered_m = extract.render(
                    client, cfg.extract_model, crop, det.label, "magenta"
                )
                rgba = matte.chroma_key_magenta(rendered_m)
                used = "magenta_fallback"

            final = matte.center_pad_square(rgba, cfg.output_size)
            final.save(out_path, "PNG")

            extracted += 1
            run_log.write(
                screenshot=screenshot_path.name,
                stage="extract",
                status="ok",
                key=key,
                label=det.label,
                idx=idx,
                bbox=list(bbox),
                matte=used,
                model=cfg.extract_model,
                latency_ms=int((time.time() - t0) * 1000),
                out=str(out_path.relative_to(cfg.output_dir)),
            )
            console.print(f"  [green]✓[/green] {out_path.name} ({used})")
        except Exception as e:
            failed += 1
            run_log.write(
                screenshot=screenshot_path.name,
                stage="extract",
                status="error",
                key=key,
                label=det.label,
                idx=idx,
                bbox=list(bbox),
                error=str(e),
            )
            if cfg.verbose:
                console.print(f"  [red]✗[/red] {out_path.name}: {e}")
                console.print(f"    {traceback.format_exc()}")
            else:
                console.print(f"  [red]✗[/red] {out_path.name}: {e}")

    return {"detected": len(items), "extracted": extracted, "failed": failed}


def iter_screenshots(input_dir: Path) -> list[Path]:
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    return sorted(p for p in input_dir.iterdir() if p.suffix.lower() in exts)


def run(cfg: RunConfig) -> None:
    from .client import make_client

    client = make_client()
    shots = iter_screenshots(cfg.input_dir)
    if not shots:
        console.print(f"[yellow]no screenshots in {cfg.input_dir}[/yellow]")
        return

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    log_path = cfg.output_dir / "_run.jsonl"
    totals = {"detected": 0, "extracted": 0, "failed": 0}

    with RunLog(log_path) as rlog:
        for i, shot in enumerate(shots, start=1):
            console.print(f"\n[cyan][{i}/{len(shots)}][/cyan] {shot.name}")
            stats = process_screenshot(client, shot, cfg, rlog)
            for k, v in stats.items():
                totals[k] += v

    console.print(
        f"\n[bold green]done[/bold green] — "
        f"{totals['detected']} detected, "
        f"{totals['extracted']} extracted, "
        f"{totals['failed']} failed"
    )
