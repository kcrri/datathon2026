"""Backtest the sell/buy guard verdicts against what the price did next.

Each verdict makes a testable claim about the days that follow:

  sell  panic_risk          the drop was crowd-driven      -> price recovers (forward return > 0)
  sell  evidence_supported  the data backs the concern     -> price keeps falling (forward return <= 0)
  buy   dip_with_context    market-driven dip              -> price recovers (forward return > 0)
  buy   falling_knife       company trouble                -> price keeps falling (forward return <= 0)
  buy   chasing_risk        hype-driven rally              -> gains fade (forward return <= 0)

``no_signal`` and ``mixed`` make no claim, so they are counted but not scored.
The forward return runs from the verdict day's close to the last close available.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Sequence

try:
    from . import sell_guard
except ImportError:  # pragma: no cover
    import sell_guard

# verdict -> does the claim hold when the forward return is positive?
CLAIMS: Dict[tuple[str, str], bool] = {
    ("sell", "panic_risk"): True,
    ("sell", "evidence_supported"): False,
    ("buy", "dip_with_context"): True,
    ("buy", "falling_knife"): False,
    ("buy", "chasing_risk"): False,
}


def _closes(change_prices: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for row in change_prices:
        out.setdefault(row["ticker"], {})[row["date"]] = float(row["close"])
    return out


def backtest(
    current_prices: Sequence[Mapping[str, Any]],
    change_prices: Sequence[Mapping[str, Any]],
    news: Sequence[Mapping[str, Any]],
    peers: Optional[Mapping[str, Sequence[str]]] = None,
    half_life_days: Optional[float] = None,
) -> Dict[str, Any]:
    """Evaluate every ticker, action and day but the last, and score each claim."""
    closes = _closes(change_prices)
    dates = sorted({r["date"] for r in change_prices})
    rows: List[Dict[str, Any]] = []
    for as_of in dates[:-1]:
        for ticker, series in closes.items():
            if as_of not in series or dates[-1] not in series:
                continue
            forward = series[dates[-1]] / series[as_of] - 1
            for action in ("sell", "buy"):
                try:
                    result = sell_guard.evaluate_trade(
                        action, ticker, current_prices, change_prices, news, as_of,
                        peers=peers, half_life_days=half_life_days,
                    )
                except ValueError:
                    continue
                claim = CLAIMS.get((action, result["verdict"]))
                rows.append(
                    {
                        "as_of": as_of,
                        "ticker": ticker,
                        "action": action,
                        "verdict": result["verdict"],
                        "forward_return_pct": round(forward * 100, 2),
                        "scored": claim is not None,
                        "correct": None if claim is None else (forward > 0) == claim,
                    }
                )
    scored = [r for r in rows if r["scored"]]
    by_verdict: Dict[str, Dict[str, int]] = {}
    for r in scored:
        entry = by_verdict.setdefault(f"{r['action']}:{r['verdict']}", {"n": 0, "correct": 0})
        entry["n"] += 1
        entry["correct"] += bool(r["correct"])
    return {
        "evaluations": len(rows),
        "scored": len(scored),
        "unscored": len(rows) - len(scored),
        "correct": sum(bool(r["correct"]) for r in scored),
        "hit_rate": (sum(bool(r["correct"]) for r in scored) / len(scored)) if scored else None,
        "by_verdict": by_verdict,
        "rows": rows,
        "last_day": dates[-1] if dates else None,
    }
