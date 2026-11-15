"""Qualitative facts about a trade check: words, never figures.

Used wherever a language model has to talk about a trade check. The model never receives a number
it could misquote; the numbers are shown to the user from the Classifier's evidence.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

FINAL_LABELS = {
    ("sell", "panic_risk"): "panic sell",
    ("sell", "evidence_supported"): "reasoned sell",
    ("sell", "mixed"): "unclear sell",
    ("sell", "no_signal"): "calm sell",
    ("buy", "dip_with_context"): "buying after a market-wide drop",
    ("buy", "chasing_risk"): "buying out of excitement",
    ("buy", "falling_knife"): "buying into bad company news",
    ("buy", "mixed"): "unclear buy",
    ("buy", "no_signal"): "calm buy",
}


def evidence_value(result: Dict[str, Any], key: str) -> Optional[float]:
    return next((e["value"] for e in result["evidence"] if e["evidence_id"].endswith(f":{key}")), None)


def tone(value: Optional[float]) -> Optional[str]:
    return None if value is None else "upbeat" if value >= 0.3 else "negative" if value <= -0.3 else "neutral"


def evidence_ids(result: Dict[str, Any]) -> List[str]:
    return [e["evidence_id"] for e in result["evidence"] if e["value"] is not None]


def qualitative(action: str, result: Dict[str, Any]) -> Dict[str, Any]:
    ev = lambda key: evidence_value(result, key)  # noqa: E731
    drop, rise = -(ev("drop") or 0), ev("rise") or 0
    move, volume, breadth, hype = max(drop, rise), ev("volume") or 1, ev("breadth") or 0, ev("hype") or 0
    return {
        "ticker": result["ticker"],
        "action": action,
        "final_verdict": FINAL_LABELS.get((action, result["verdict"]), result["verdict"]),
        "driver": {"market": "the whole market or the crowd", "company": "the company itself", "mixed": "a mix of both"}[result.get("driver", "mixed")],
        "price_move": "barely moved" if move < 3 else ("fell" if drop >= rise else "rose") + (" a lot" if move < 8 else " very sharply"),
        "trading_activity": "very busy" if volume >= 2 else "busy" if volume >= 1.25 else "normal",
        "other_investments_falling": "most" if breadth >= 60 else "many" if breadth >= 30 else "few",
        "news_is_about": "this company" if (ev("company_news") or 0) > 50 else "the whole market",
        "news_tone": tone(ev("sentiment")),
        "similar_investments_news_tone": tone(ev("peer_sentiment")),
        "excitement_in_market": "high" if hype >= 55 else "medium" if hype >= 35 else "low",
    }
