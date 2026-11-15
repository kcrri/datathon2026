#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hackathon_info" / "alphaforge_starter"
MANIFEST = ROOT / "data" / "manifests" / "starter-v1.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("dataset_id") != "alphaforge-starter-v1":
        raise SystemExit("unexpected dataset_id in starter manifest")
    if manifest.get("s3_prefix") != "starter/v1":
        raise SystemExit("unexpected s3_prefix in starter manifest")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise SystemExit("starter manifest has no file records")
    for record in files:
        path = SOURCE / record["name"]
        if not path.is_file():
            raise SystemExit(f"missing starter file: {record['name']}")
        body = path.read_bytes()
        if len(body) != record["bytes"]:
            raise SystemExit(f"byte count mismatch: {record['name']}")
        if hashlib.sha256(body).hexdigest() != record["sha256"]:
            raise SystemExit(f"SHA-256 mismatch: {record['name']}")

    print(f"verified {len(files)} starter files against {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
