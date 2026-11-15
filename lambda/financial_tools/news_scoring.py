"""Classify headlines with Amazon Bedrock inside the Lambda and save the scores to S3.

Each headline gets a sentiment (-1..1), a scope (company or market) and a category from every
configured model; the sentiment is the median of the votes, scope and category are majority
votes, and the spread between models is saved. Scores are precomputed here, never at request
time, and temperature 0 keeps reruns stable.
"""

from __future__ import annotations

import csv
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Mapping, Sequence

try:
    from . import market_store, sentiment_tools
except ImportError:  # Lambda CodeUri places modules at the runtime root.
    import market_store
    import sentiment_tools

MAX_WORKERS = 4  # stays inside the workshop Bedrock rate limits

SYSTEM = """You classify short financial news headlines for an investor who holds one ticker.
Return JSON only: {"sentiment": <number from -1.0 to 1.0>, "scope": "company" or "market", "category": <one of CATEGORIES>}.
sentiment: how good or bad the headline is for holders of that ticker (-1 very bad, 0 neutral, 1 very good).
scope: "company" if the headline is about that specific company's own business, regulators, ratings or
operations; "market" if it is about the broader market, a sector, rates, the economy or investor mood.
category: the main topic. One of: """ + ", ".join(sentiment_tools.CATEGORIES) + """.
Use "market" for market-wide, sector or macro news. Judge only the headline. No explanation."""


def parse(text: str) -> tuple[float, str, str]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"no JSON in model output: {text!r}")
    value = json.loads(match.group(0))
    sentiment = float(value["sentiment"])
    scope = value["scope"]
    category = value.get("category", "other")
    if not -1.0 <= sentiment <= 1.0 or scope not in ("company", "market"):
        raise ValueError(f"out-of-range model output: {value}")
    if category not in sentiment_tools.CATEGORIES:
        category = "other"
    return round(sentiment, 2), scope, category


def score_headline(client: Any, model_ids: Sequence[str], prompt: str) -> Dict[str, Any]:
    """Ask every model, then combine: median sentiment, majority scope and category."""
    votes = []
    for model_id in model_ids:
        response = client.converse(
            modelId=model_id,
            system=[{"text": SYSTEM}],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 80},
        )
        votes.append(parse(response["output"]["message"]["content"][0]["text"]))
    combined = sentiment_tools.aggregate_votes([v[0] for v in votes])
    return {
        "sentiment": combined["sentiment"],
        "scope": sentiment_tools.majority_label([v[1] for v in votes]),
        "category": sentiment_tools.majority_label([v[2] for v in votes]),
        "spread": combined["spread"],
        "agreement": combined["agreement"],
    }


def score_market_news(
    stores: market_store.MarketStores,
    client: Any,
    model_ids: Sequence[str],
    folders: Sequence[str] = market_store.FOLDERS,
    names: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Score ``<folder>/news.csv`` and write ``<folder>/news_scored.csv`` to the market store."""
    if not model_ids:
        raise ValueError("at least one Bedrock model id is required")
    bad = [f for f in folders if f not in market_store.FOLDERS]
    if bad:
        raise ValueError(f"unsupported folder: {bad[0]}")
    names = names or market_store.load_market(stores)["names"]

    summary: Dict[str, Any] = {"folders": {}, "disagreements": [], "model_ids": list(model_ids)}
    agree = total = 0
    for folder in folders:
        body, source = stores.market.read(f"{folder}/news.csv")
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8"))))

        def one(row: Dict[str, str]) -> Dict[str, Any]:
            prompt = f"Ticker: {row['ticker']} ({names.get(row['ticker'], row['ticker'])})\nHeadline: {row['headline']}"
            return score_headline(client, model_ids, prompt)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            results = list(pool.map(one, rows))
        out = io.StringIO()
        fields = ["date", "ticker", "headline", "scope", "label_scope", "category", "sentiment", "model_spread", "model_agreement", "model_id", "source"]
        writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row, result in zip(rows, results):
            total += 1
            agree += result["scope"] == row["scope"]
            if not result["agreement"]:
                summary["disagreements"].append({"ticker": row["ticker"], "headline": row["headline"], "spread": result["spread"]})
            writer.writerow(
                {
                    "date": row["date"], "ticker": row["ticker"], "headline": row["headline"],
                    "scope": result["scope"], "label_scope": row["scope"], "category": result["category"],
                    "sentiment": result["sentiment"], "model_spread": result["spread"],
                    "model_agreement": result["agreement"], "model_id": "+".join(model_ids), "source": row["source"],
                }
            )
        summary["folders"][folder] = {"headlines": len(rows), "written": stores.market.write(f"{folder}/news_scored.csv", out.getvalue().encode("utf-8"))}
    market_store.clear_cache()
    summary["scope_agreement"] = {"agree": agree, "total": total}
    return summary
