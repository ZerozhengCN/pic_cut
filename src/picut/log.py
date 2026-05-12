"""Console logging (rich) and JSONL run log."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


@dataclass
class RunLog:
    path: Path
    _f: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = self.path.open("a", encoding="utf-8")

    def write(self, **fields: Any) -> None:
        rec = {"ts": time.time(), **fields}
        self._f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._f.flush()

    def close(self) -> None:
        if self._f is not None:
            self._f.close()
            self._f = None

    def __enter__(self) -> "RunLog":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


def completed_keys(jsonl_path: Path) -> set[str]:
    """Return set of '{screenshot}|{bbox_hash}' keys with status=ok."""
    if not jsonl_path.exists():
        return set()
    out: set[str] = set()
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("status") == "ok" and "key" in rec:
                out.add(rec["key"])
    return out
