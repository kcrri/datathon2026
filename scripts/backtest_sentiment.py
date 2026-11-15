#!/usr/bin/env python3
"""Backtest sell-guard verdicts against the price moves that follow them.

    python3 scripts/backtest_sentiment.py [--half-life 3]

Uses the two simulated datasets and (if present) the scored headlines. No AWS calls.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

import backtest  # noqa: E402
import sentiment_tools  # noqa: E402

SIM = ROOT / "data" / "simulated"
UNIVERSE = ROOT / "hackathon_info" / "alphaforge_starter" / "assets_universe.csv"


def rows(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def news(folder: str) -> list[dict]:
    scored = SIM / folder / "news_scored.csv"
    return rows(scored if scored.exists() else SIM / folder / "news.csv")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--half-life", type=float, default=None, help="days; omit for plain mean sentiment")
    args = parser.parse_args()
    peers = sentiment_tools.peer_groups(rows(UNIVERSE))
    result = backtest.backtest(
        rows(SIM / "current" / "prices.csv"),
        rows(SIM / "marketchange" / "prices.csv"),
        news("current") + news("marketchange"),
        peers=peers,
        half_life_days=args.half_life,
    )
    print(f"Forward return measured to {result['last_day']}")
    print(f"{result['evaluations']} evaluations: {result['scored']} made a testable claim, {result['unscored']} did not")
    for key, entry in sorted(result["by_verdict"].items()):
        print(f"  {key:30} {entry['correct']}/{entry['n']} held")
    rate = result["hit_rate"]
    print("hit rate:", "n/a" if rate is None else f"{rate:.0%} ({result['correct']}/{result['scored']})")
    print("\nCaution: the datasets are simulated and cover a few days, so this checks the logic, not predictive skill.")


if __name__ == "__main__":
    main()
