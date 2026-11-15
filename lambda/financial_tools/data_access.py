from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Dict, Iterable, List, Mapping, Tuple


@dataclass(frozen=True)
class PriceObservation:
    observation_date: date
    ticker: str
    adjusted_close: float
    currency: str


@dataclass
class MarketDataset:
    prices: Dict[str, List[PriceObservation]]
    fx_dates: List[date]
    fx_rates: List[float]
    sources: List[str]

    def prior_usdcad(self, observation_date: date) -> float:
        position = bisect_right(self.fx_dates, observation_date) - 1
        if position < 0:
            raise ValueError(f"no USD/CAD rate on or before {observation_date}")
        return self.fx_rates[position]


def _read_csv(text: str) -> Iterable[dict[str, str]]:
    return csv.DictReader(io.StringIO(text))


def dataset_from_csv_text(
    prices_text: str,
    fx_text: str,
    sources: List[str] | None = None,
) -> MarketDataset:
    prices: Dict[str, List[PriceObservation]] = {}
    for row in _read_csv(prices_text):
        observation = PriceObservation(
            observation_date=date.fromisoformat(row["date"]),
            ticker=row["ticker"],
            adjusted_close=float(row["adj_close"]),
            currency=row["currency"],
        )
        if observation.adjusted_close <= 0:
            raise ValueError(
                f"non-positive adjusted close for {observation.ticker} on {observation.observation_date}"
            )
        prices.setdefault(observation.ticker, []).append(observation)

    for ticker, observations in prices.items():
        observations.sort(key=lambda item: item.observation_date)
        dates = [item.observation_date for item in observations]
        if len(dates) != len(set(dates)):
            raise ValueError(f"duplicate price dates for {ticker}")

    fx_rows = sorted(
        (
            (date.fromisoformat(row["date"]), float(row["usdcad"]))
            for row in _read_csv(fx_text)
        ),
        key=lambda item: item[0],
    )
    if not fx_rows:
        raise ValueError("USD/CAD dataset is empty")
    fx_dates = [item[0] for item in fx_rows]
    if len(fx_dates) != len(set(fx_dates)):
        raise ValueError("duplicate USD/CAD dates")
    if any(rate <= 0 for _, rate in fx_rows):
        raise ValueError("USD/CAD rates must be positive")

    return MarketDataset(
        prices=prices,
        fx_dates=fx_dates,
        fx_rates=[item[1] for item in fx_rows],
        sources=sources or [],
    )
def _verify_manifest(
    manifest: dict,
    objects: Mapping[str, bytes],
    expected_dataset_id: str,
    expected_prefix: str,
) -> None:
    if manifest.get("dataset_id") != expected_dataset_id:
        raise ValueError("dataset manifest ID does not match DATASET_ID")
    if str(manifest.get("s3_prefix", "")).strip("/") != expected_prefix:
        raise ValueError("dataset manifest prefix does not match DATA_PREFIX")
    records = manifest.get("files")
    if not isinstance(records, list):
        raise ValueError("dataset manifest files must be a list")
    indexed = {
        item.get("name"): item
        for item in records
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    for name, body in objects.items():
        record = indexed.get(name)
        if record is None:
            raise ValueError(f"dataset manifest is missing {name}")
        if record.get("bytes") != len(body):
            raise ValueError(f"dataset byte count does not match manifest for {name}")
        digest = hashlib.sha256(body).hexdigest()
        if record.get("sha256") != digest:
            raise ValueError(f"dataset checksum does not match manifest for {name}")


def _get_s3_object(client, bucket: str, key: str) -> Tuple[bytes, str]:
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read()
    version = response.get("VersionId") or response.get("ETag", "").strip('"')
    source = f"s3://{bucket}/{key}#{version}" if version else f"s3://{bucket}/{key}"
    return body, source


@lru_cache(maxsize=1)
def load_dataset_from_s3() -> MarketDataset:
    bucket = os.getenv("DATA_BUCKET")
    prefix = os.getenv("DATA_PREFIX", "starter/v1").strip("/")
    dataset_id = os.getenv("DATASET_ID", "alphaforge-starter-v1")
    if not bucket:
        raise RuntimeError("DATA_BUCKET is required")

    import boto3

    client = boto3.client("s3")
    prices_body, prices_source = _get_s3_object(
        client, bucket, f"{prefix}/prices_daily.csv"
    )
    fx_body, fx_source = _get_s3_object(
        client, bucket, f"{prefix}/fx_usdcad_daily.csv"
    )
    manifest_body, manifest_source = _get_s3_object(
        client, bucket, f"{prefix}/manifest.json"
    )
    manifest = json.loads(manifest_body.decode("utf-8"))
    _verify_manifest(
        manifest,
        {
            "prices_daily.csv": prices_body,
            "fx_usdcad_daily.csv": fx_body,
        },
        expected_dataset_id=dataset_id,
        expected_prefix=prefix,
    )
    return dataset_from_csv_text(
        prices_body.decode("utf-8"),
        fx_body.decode("utf-8"),
        sources=[prices_source, fx_source, manifest_source],
    )
