#!/usr/bin/env python3
"""Build or check the integrity manifest for the simulated market data uploaded to S3.

    python3 scripts/build_market_manifest.py          write data/manifests/simulated-v1.json
    python3 scripts/build_market_manifest.py --check  verify the files against the manifest

The Lambda re-verifies these checksums every time it loads the data from S3. Scored headlines
(news_scored.csv) are written by the Lambda itself and are not part of the manifest.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "simulated"
OUTPUT = ROOT / "data" / "manifests" / "simulated-v1.json"
FILES = [f"{folder}/{name}" for folder in ("current", "marketchange") for name in ("prices.csv", "news.csv")]


def record(name: str) -> dict:
    raw = (SOURCE / name).read_bytes()
    return {"name": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main() -> int:
    if "--check" in sys.argv:
        manifest = json.loads(OUTPUT.read_text())
        bad = [r["name"] for r in manifest["files"] if record(r["name"]) != {k: r[k] for k in ("name", "bytes", "sha256")}]
        print("manifest matches the files" if not bad else f"changed since the manifest: {', '.join(bad)}")
        return 1 if bad else 0
    manifest = {
        "dataset_id": "simulated-market-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_directory": "data/simulated",
        "s3_prefix": "simulated/v1",
        "files": [record(name) for name in FILES],
        "notes": ["Fictional price moves and headlines for demonstration. Not real market data."],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n")
    print(OUTPUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
