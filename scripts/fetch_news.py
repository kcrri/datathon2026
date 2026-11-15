#!/usr/bin/env python3
"""Fetch real headlines for the tracked tickers from NewsAPI (https://newsapi.org).

    NEWSAPI_KEY=... python3 scripts/fetch_news.py --days 7

Writes data/real/news.csv with the same columns as the simulated news
(date,ticker,scope,headline,source). ``scope`` is left as "company" and no sentiment is added:
the Lambda classifies the simulated headlines only, and scoring real headlines there is not
wired up yet. The API key is read from the environment and never printed or stored.
The free NewsAPI plan only returns recent articles and may delay them.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "hackathon_info" / "alphaforge_starter" / "assets_universe.csv"
OUT = ROOT / "data" / "real" / "news.csv"
ENDPOINT = "https://newsapi.org/v2/everything"
PER_TICKER = 5


def universe() -> dict[str, str]:
    with UNIVERSE.open(newline="") as handle:
        return {r["ticker"]: r["name"] for r in csv.DictReader(handle)}


def fetch(query: str, since: date, key: str) -> list[dict]:
    params = urllib.parse.urlencode(
        {"q": f'"{query}"', "from": since.isoformat(), "language": "en", "sortBy": "publishedAt", "pageSize": PER_TICKER}
    )
    request = urllib.request.Request(f"{ENDPOINT}?{params}", headers={"X-Api-Key": key})
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 (fixed https endpoint)
        payload = json.load(response)
    if payload.get("status") != "ok":
        raise RuntimeError(f"NewsAPI error: {payload.get('code')}")
    return payload.get("articles", [])


def to_rows(ticker: str, articles: list[dict]) -> list[dict]:
    rows = []
    for article in articles:
        title = (article.get("title") or "").strip()
        published = (article.get("publishedAt") or "")[:10]
        if not title or not published or title == "[Removed]":
            continue
        outlet = (article.get("source") or {}).get("name") or "unknown"
        rows.append({"date": published, "ticker": ticker, "scope": "company", "headline": title, "source": f"NewsAPI:{outlet}"})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--tickers", nargs="*", help="limit to these tickers (default: the equities in the universe)")
    args = parser.parse_args()
    key = os.environ.get("NEWSAPI_KEY")
    if not key:
        print("Set NEWSAPI_KEY in your environment (never commit it).", file=sys.stderr)
        return 1
    names = universe()
    tickers = args.tickers or [t for t in names if "-" not in t]  # skip crypto pairs
    since = date.today() - timedelta(days=args.days)
    out: list[dict] = []
    for ticker in tickers:
        found = to_rows(ticker, fetch(names[ticker], since, key))
        out.extend(found)
        print(f"{ticker:8} {len(found)} headlines")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "ticker", "scope", "headline", "source"])
        writer.writeheader()
        writer.writerows(out)
    print(f"wrote {len(out)} headlines to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
