"""Phase 3 reporting helpers."""

from __future__ import annotations

import json
from pathlib import Path


def write_evaluation_report(report: dict, output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination
