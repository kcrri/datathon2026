"""Deterministic sentiment helpers shared by the backend, scripts and AWS Lambda.

Pure functions over plain rows. Nothing here calls a model: headline scores
(sentiment, scope, category) are produced upstream by ``scripts/score_news_sentiment.py``
and arrive as columns. These helpers only combine them.

  taxonomy     split company news into earnings / regulatory / legal / ... categories
  decay        older headlines count less (exponential half-life)
  peers        sentiment of related tickers (same sector or asset group)
  voting       combine scores from several models and report their disagreement
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

# Company news is split into the subcategories below. "market" covers broad-market,
# sector and macro headlines (the existing ``scope == "market"`` rows).
CATEGORIES = (
    "earnings",
    "dividend",
    "regulatory",
    "legal",
    "credit_rating",
    "analyst",
    "leadership",
    "competitor",
    "operations",
    "market",
    "other",
)

# First matching rule wins, so more specific topics come before generic ones.
_KEYWORDS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("credit_rating", ("rating agency", "downgrade", "upgrade", "credit rating", "outlook revised")),
    ("regulatory", ("regulator", "regulatory", "rate filing", "safety review", "license", "licence", "approval", "antitrust")),
    ("legal", ("lawsuit", "sues", "settlement", "court", "investigation", "probe", "fine ")),
    ("dividend", ("dividend", "payout", "buyback")),
    ("earnings", ("earnings", "quarterly", "revenue", "profit", "guidance", "results", "merchant growth", "demand")),
    ("leadership", ("ceo", "chief executive", "chairman", "resigns", "appoints", "executive")),
    ("analyst", ("analyst", "price target", "initiates coverage")),
    ("competitor", ("rival", "competitor", "peer ", "market share")),
    ("operations", ("shutdown", "halt", "repair", "volumes", "shipments", "outage", "recall", "supply", "production")),
)

DEFAULT_HALF_LIFE_DAYS = 3.0
AGREEMENT_SPREAD = 0.4  # models agree when their scores span no more than this


def _day(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def classify_category(headline: str, scope: str = "company") -> str:
    """Rule-based category for a headline, used when no model category is present."""
    if scope == "market":
        return "market"
    text = f" {headline.lower()} "
    for category, words in _KEYWORDS:
        if any(word in text for word in words):
            return category
    return "other"


def row_category(row: Mapping[str, Any]) -> str:
    """The model's category when valid, otherwise the keyword classification."""
    given = (row.get("category") or "").strip()
    if given in CATEGORIES:
        return given
    return classify_category(row.get("headline", ""), row.get("scope", "company"))


def category_breakdown(rows: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    """Headline count per category (only categories that occur)."""
    counts: Dict[str, int] = {}
    for row in rows:
        category = row_category(row)
        counts[category] = counts.get(category, 0) + 1
    return counts


def decay_weight(age_days: float, half_life_days: float) -> float:
    """Weight of a headline ``age_days`` old: 1.0 today, 0.5 after one half-life."""
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    return 0.5 ** (max(age_days, 0.0) / half_life_days)


def weighted_sentiment(
    rows: Iterable[Mapping[str, Any]], as_of: str | date, half_life_days: Optional[float] = None
) -> Optional[float]:
    """Mean sentiment; with ``half_life_days`` set, recent headlines weigh more."""
    cutoff = _day(as_of)
    pairs: List[tuple[float, float]] = []
    for row in rows:
        if row.get("sentiment") in (None, ""):
            continue
        weight = 1.0
        if half_life_days is not None:
            weight = decay_weight((cutoff - _day(row["date"])).days, half_life_days)
        pairs.append((float(row["sentiment"]), weight))
    if not pairs:
        return None
    total = sum(w for _, w in pairs)
    return sum(s * w for s, w in pairs) / total if total else None


def peer_groups(universe: Iterable[Mapping[str, Any]]) -> Dict[str, List[str]]:
    """Ticker -> related tickers, grouped by sector or asset group.

    "Broad market (U.S.)" and "Broad market (Canada)" share one group, as do the
    bond funds, so an index selloff counts as news for every other index fund.
    """
    groups: Dict[str, List[str]] = {}
    for row in universe:
        key = (row.get("sector") or row.get("asset_class") or "").split("(")[0].strip().lower()
        if key:
            groups.setdefault(key, []).append(row["ticker"])
    peers: Dict[str, List[str]] = {}
    for members in groups.values():
        for ticker in members:
            peers[ticker] = [m for m in members if m != ticker]
    return peers


def peer_sentiment(
    news: Sequence[Mapping[str, Any]],
    ticker: str,
    peers: Mapping[str, Sequence[str]],
    since: str | date,
    as_of: str | date,
    half_life_days: Optional[float] = None,
) -> Dict[str, Any]:
    """Cross-ticker signal: sentiment of related tickers' headlines in the window.

    Reported as evidence only. A peer's company-specific news is informative about
    the group, so each peer's score is averaged equally (one vote per peer with news).
    """
    start, cutoff = _day(since), _day(as_of)
    scores: Dict[str, float] = {}
    for peer in peers.get(ticker, []):
        rows = [n for n in news if n["ticker"] == peer and start <= _day(n["date"]) <= cutoff]
        value = weighted_sentiment(rows, cutoff, half_life_days)
        if value is not None:
            scores[peer] = value
    return {
        "peer_sentiment": statistics.fmean(scores.values()) if scores else None,
        "peer_count": len(peers.get(ticker, [])),
        "peers_with_news": sorted(scores),
    }


def aggregate_votes(votes: Sequence[float]) -> Dict[str, Any]:
    """Combine several models' sentiment scores for one headline.

    The median is robust to one outlier model. ``spread`` and ``agreement`` report
    how much the models disagreed, so disputed headlines can be flagged.
    """
    values = [float(v) for v in votes if v is not None]
    if not values:
        return {"sentiment": None, "spread": None, "agreement": False, "votes": 0}
    spread = max(values) - min(values)
    return {
        "sentiment": round(statistics.median(values), 2),
        "spread": round(spread, 2),
        "agreement": spread <= AGREEMENT_SPREAD,
        "votes": len(values),
    }


def majority_label(labels: Sequence[str]) -> str:
    """Most common label; ties resolve to the label seen first (stable)."""
    counts: Dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    best = max(counts.values())
    return next(label for label in labels if counts[label] == best)
