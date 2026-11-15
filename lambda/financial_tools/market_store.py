"""Where the simulated market data lives.

Deployed, every byte comes from a private, versioned S3 bucket, so every user and every
backend instance sees the same data. A local folder store exists only so tests and offline
development can run the same code without AWS; nothing selects it unless asked to.

Layout (the same under S3 ``<prefix>/`` and the local folder):

    current/prices.csv        current/news.csv        current/news_scored.csv
    marketchange/prices.csv   marketchange/news.csv   marketchange/news_scored.csv

``news_scored.csv`` is written by the scoring operation; the other files are immutable inputs
verified against ``manifest.json`` (sha256) when read from S3.
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from . import sentiment_tools
    from .data_access import _verify_manifest
except ImportError:  # Lambda CodeUri places modules at the runtime root.
    import sentiment_tools
    from data_access import _verify_manifest

FOLDERS = ("current", "marketchange")
IMMUTABLE_FILES = tuple(f"{folder}/{name}" for folder in FOLDERS for name in ("prices.csv", "news.csv"))
CACHE_SECONDS = 60.0  # a warm container picks up newly scored headlines within a minute


class LocalStore:
    kind = "local"

    def __init__(self, root: Path):
        self.root = Path(root)

    @property
    def label(self) -> str:
        return f"file://{self.root}"

    def read(self, name: str) -> Tuple[bytes, str]:
        path = self.root / name
        try:
            return path.read_bytes(), f"file://{path}"
        except OSError as exc:
            raise RuntimeError(f"cannot read {path}") from exc

    def write(self, name: str, body: bytes) -> str:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return f"file://{path}"


class S3Store:
    kind = "s3"

    def __init__(self, bucket: str, prefix: str, client: Any = None):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("s3")
        return self._client

    @property
    def label(self) -> str:
        return f"s3://{self.bucket}/{self.prefix}"

    def _key(self, name: str) -> str:
        return f"{self.prefix}/{name}"

    def read(self, name: str) -> Tuple[bytes, str]:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key(name))
        except Exception as exc:  # botocore ClientError and friends
            raise RuntimeError(f"cannot read s3://{self.bucket}/{self._key(name)}") from exc
        version = response.get("VersionId") or str(response.get("ETag", "")).strip('"')
        source = f"s3://{self.bucket}/{self._key(name)}" + (f"#{version}" if version else "")
        return response["Body"].read(), source

    def write(self, name: str, body: bytes) -> str:
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=self._key(name), Body=body, ContentType="text/csv"
            )
        except Exception as exc:
            raise RuntimeError(f"cannot write s3://{self.bucket}/{self._key(name)}") from exc
        return f"s3://{self.bucket}/{self._key(name)}"


@dataclass
class MarketStores:
    market: Any  # simulated prices and headlines
    reference: Any  # starter reference data (the asset universe)


def stores_from_env() -> MarketStores:
    """Deployed configuration: S3 only. Raises when the bucket is not configured."""
    bucket = os.getenv("DATA_BUCKET")
    if not bucket:
        raise RuntimeError("DATA_BUCKET is required")
    return MarketStores(
        market=S3Store(bucket, os.getenv("MARKET_PREFIX", "simulated/v1")),
        reference=S3Store(bucket, os.getenv("DATA_PREFIX", "starter/v1")),
    )


def _rows(text: str) -> List[Dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def _text(store: Any, name: str, sources: List[str]) -> str:
    body, source = store.read(name)
    sources.append(source)
    return body.decode("utf-8")


_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def clear_cache() -> None:
    _CACHE.clear()


def load_market(stores: MarketStores) -> Dict[str, Any]:
    key = f"{stores.market.label}|{stores.reference.label}"
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]

    sources: List[str] = []
    if stores.market.kind == "s3":
        manifest_body, manifest_source = stores.market.read("manifest.json")
        sources.append(manifest_source)
        bodies = {name: stores.market.read(name)[0] for name in IMMUTABLE_FILES}
        _verify_manifest(
            json.loads(manifest_body.decode("utf-8")),
            bodies,
            expected_dataset_id=os.getenv("MARKET_DATASET_ID", "simulated-market-v1"),
            expected_prefix=stores.market.prefix,
        )

    def news(folder: str) -> List[Dict[str, str]]:
        """Scored headlines when they exist, otherwise the raw ones (scores are then empty)."""
        try:
            return _rows(_text(stores.market, f"{folder}/news_scored.csv", sources))
        except RuntimeError:  # not scored yet (S3 answers AccessDenied or NoSuchKey for a missing key)
            return _rows(_text(stores.market, f"{folder}/news.csv", sources))

    current = _rows(_text(stores.market, "current/prices.csv", sources))
    change = _rows(_text(stores.market, "marketchange/prices.csv", sources))
    universe = _rows(_text(stores.reference, "assets_universe.csv", sources))
    data = {
        "current": current,
        "change": change,
        "news": news("current") + news("marketchange"),
        "dates": sorted({r["date"] for r in change}),
        "universe": universe,
        "names": {r["ticker"]: r["name"] for r in universe},
        "peers": sentiment_tools.peer_groups(universe),
        "sources": sources,
    }
    _CACHE[key] = (time.monotonic(), data)
    return data
