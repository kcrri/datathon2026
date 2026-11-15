#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hackathon_info" / "alphaforge_starter"
OUTPUT = ROOT / "data" / "manifests" / "starter-v1.json"
FILES = [
    "assets_universe.csv",
    "prices_daily.csv",
    "corporate_actions.csv",
    "fx_usdcad_daily.csv",
    "macro_rates.csv",
    "sources_metadata.csv",
]


def record(path: Path) -> dict:
    raw = path.read_bytes()
    with path.open(newline="", encoding="utf-8") as handle:
        rows = sum(1 for _ in csv.reader(handle)) - 1
    return {
        "name": path.name,
        "bytes": len(raw),
        "rows": rows,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def main() -> None:
    missing = [name for name in FILES if not (SOURCE / name).exists()]
    if missing:
        raise SystemExit(f"missing starter files: {', '.join(missing)}")
    manifest = {
        "dataset_id": "alphaforge-starter-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_directory": "hackathon_info/alphaforge_starter",
        "s3_prefix": "starter/v1",
        "files": [record(SOURCE / name) for name in FILES],
        "quality_notes": [
            "Adjusted close is used for historical returns.",
            "USD listings require dated USD/CAD conversion.",
            "Trading calendars are not aligned in the source data.",
            "Monthly macro dates are reference dates, not publication dates.",
            "The asset universe has survivorship and selection bias.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
