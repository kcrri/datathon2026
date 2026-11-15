"""Feature flags: which dashboard pages are switched on.

The page list lives in the frontend registry (``frontend/src/features/registry.ts``);
this module only stores an on/off flag per page id. Flags are kept in memory and
saved to a small JSON file so an admin's choices survive a backend restart.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

FEATURE_IDS = ("analysis", "holdings", "assistant", "accounts", "insights")

DEFAULT_PATH = Path(__file__).resolve().parents[2] / ".runtime" / "features.json"


def _path() -> Path:
    return Path(os.getenv("FEATURES_FILE", DEFAULT_PATH))


def _defaults() -> Dict[str, bool]:
    return {feature_id: True for feature_id in FEATURE_IDS}


def flags() -> Dict[str, bool]:
    """Current flags. Unknown ids in the file are ignored; missing ids default to on."""
    current = _defaults()
    path = _path()
    if path.exists():
        try:
            saved = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            saved = {}
        for feature_id in FEATURE_IDS:
            if isinstance(saved.get(feature_id), bool):
                current[feature_id] = saved[feature_id]
    return current


def _save(current: Dict[str, bool]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2) + "\n")


def set_flag(feature_id: str, enabled: bool) -> Dict[str, bool]:
    if feature_id not in FEATURE_IDS:
        raise KeyError(feature_id)
    current = flags()
    current[feature_id] = enabled
    _save(current)
    return current


def reset() -> Dict[str, bool]:
    current = _defaults()
    _save(current)
    return current
