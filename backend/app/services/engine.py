"""Run a market or calculation operation where it belongs: in the AWS Lambda.

Deployed (the default), every operation is an invocation of the financial-tools Lambda, which
reads the market data from S3 and calls Bedrock for classification. The backend keeps no
market data and no market state, so every user and every backend instance gets the same
answer. ``ENGINE=local`` runs the identical code against a local folder and exists only for
tests and offline development; it is never chosen silently.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

from app.services import lambda_tools
from app.services.errors import ExternalServiceError, ServiceConfigurationError

ROOT = Path(__file__).resolve().parents[3]
LOCAL_MARKET_DIR = ROOT / "data" / "simulated"
LOCAL_REFERENCE_DIR = ROOT / "hackathon_info" / "alphaforge_starter"


def mode() -> str:
    value = os.getenv("ENGINE", "lambda").strip().lower()
    if value not in ("lambda", "local"):
        raise ServiceConfigurationError("ENGINE must be 'lambda' or 'local'")
    return value


def run(operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if mode() == "lambda":
        return lambda_tools.invoke(operation, payload)
    return _run_local(operation, payload)


def _run_local(operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))
    import market_store  # noqa: PLC0415
    import ops  # noqa: PLC0415

    stores = market_store.MarketStores(
        market=market_store.LocalStore(Path(os.getenv("LOCAL_MARKET_DIR", LOCAL_MARKET_DIR))),
        reference=market_store.LocalStore(Path(os.getenv("LOCAL_REFERENCE_DIR", LOCAL_REFERENCE_DIR))),
    )
    try:
        return ops.run({"operation": operation, **payload}, stores, computed_by="local-engine")
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise ExternalServiceError(f"local engine failed: {exc}") from exc
