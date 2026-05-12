"""Typer CLI entrypoint."""
from __future__ import annotations

from pathlib import Path

import typer

from .config import (
    DETECT_MODEL_DEFAULT,
    EXTRACT_MODEL_DEFAULT,
    OUTPUT_SIZE,
    RunConfig,
)
from .log import console

app = typer.Typer(add_completion=False, help="Batch icon extractor for game UI screenshots.")


def _parse_categories(s: str | None) -> list[str] | None:
    if not s:
        return None
    return [x.strip() for x in s.split(",") if x.strip()]


def _check_adc() -> None:
    """Defaults are baked into client.py; this hook stays for future ADC checks."""
    return


@app.command()
def run(
    input_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    output_dir: Path = typer.Argument(..., file_okay=False, dir_okay=True),
    categories: str = typer.Option(
        None, "--categories", help="Comma-separated subset, e.g. talent_node,ui_frame"
    ),
    padding: float = typer.Option(0.08, "--padding", min=0.0, max=0.5),
    matting: str = typer.Option(
        "auto", "--matting", help="auto | rembg | magenta"
    ),
    concurrency: int = typer.Option(4, "--concurrency", min=1, max=16),
    detect_model: str = typer.Option(DETECT_MODEL_DEFAULT, "--detect-model"),
    extract_model: str = typer.Option(EXTRACT_MODEL_DEFAULT, "--extract-model"),
    max_icons: int = typer.Option(100, "--max-icons-per-shot", min=1),
    output_size: int = typer.Option(OUTPUT_SIZE, "--output-size", min=64),
    resume: bool = typer.Option(False, "--resume"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Detect only, no extraction"),
    redetect: bool = typer.Option(False, "--redetect", help="Ignore cached detection and re-run detect"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
) -> None:
    """Run full pipeline on a folder of screenshots."""
    _check_adc()
    if matting not in {"auto", "rembg", "magenta"}:
        raise typer.BadParameter("--matting must be auto|rembg|magenta")

    cfg = RunConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        detect_model=detect_model,
        extract_model=extract_model,
        categories=_parse_categories(categories),
        padding=padding,
        matting=matting,
        concurrency=concurrency,
        resume=resume,
        dry_run=dry_run,
        redetect=redetect,
        max_icons_per_shot=max_icons,
        output_size=output_size,
        verbose=verbose,
    )

    from .pipeline import run as pipeline_run

    pipeline_run(cfg)


@app.command()
def detect(
    image: Path = typer.Argument(..., exists=True, dir_okay=False),
    output_dir: Path = typer.Option(Path("./output"), "--output-dir"),
    detect_model: str = typer.Option(DETECT_MODEL_DEFAULT, "--detect-model"),
) -> None:
    """Run detection only on a single screenshot; write overlay + JSON."""
    _check_adc()
    from PIL import Image

    from .client import make_client
    from .detect import detect as do_detect
    from .overlay import render_overlay
    from .pipeline import _save_detection_json

    out_dir = output_dir / image.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    client = make_client()
    img = Image.open(image).convert("RGB")
    items = do_detect(client, img, detect_model)
    _save_detection_json(items, out_dir / "_detection.json")
    render_overlay(img, items, out_dir / "_overlay.png")
    console.print(
        f"[green]✓[/green] {len(items)} items → {out_dir}/_overlay.png, _detection.json"
    )


@app.command()
def estimate(
    input_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    icons_per_shot: int = typer.Option(20, "--icons-per-shot"),
    detect_cost: float = typer.Option(0.04, "--detect-cost-usd"),
    extract_cost: float = typer.Option(0.067, "--extract-cost-usd"),
) -> None:
    """Estimate USD cost without making any API calls."""
    from .pipeline import iter_screenshots

    shots = iter_screenshots(input_dir)
    n = len(shots)
    total = n * (detect_cost + icons_per_shot * extract_cost)
    console.print(
        f"{n} screenshot(s) × (~${detect_cost:.3f} detect + "
        f"{icons_per_shot} × ${extract_cost:.3f} extract) = "
        f"[bold]~${total:.2f}[/bold] USD (rough)"
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
