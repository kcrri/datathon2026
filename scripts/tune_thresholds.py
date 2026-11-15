#!/usr/bin/env python3
"""Tune the sell-guard thresholds against the labelled verdicts in the simulated data.

    python3 scripts/tune_thresholds.py

Labels: ``expected_verdict_if_sold`` (first and last day) and ``expected_verdict_if_bought``
(last day) from data/simulated/marketchange/dataset.json. Only 22 labelled cases exist, so
this is a robustness check, not a fit: it grid-searches the three thresholds that decide
panic_risk, finds every setting that reproduces all labels, and recommends the CENTRE of the
largest all-correct region so small changes in the data do not flip verdicts. The score
weights inside score_signals are fixed by design and are not tuned.
"""
from __future__ import annotations

import csv
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

import sell_guard  # noqa: E402

SIM = ROOT / "data" / "simulated"
GRID = {
    "NET_DECISION_MARGIN": [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40],
    "DROP_THRESHOLD_PCT": [-1.0, -2.0, -3.0, -4.0, -5.0, -6.0, -8.0],
    "VOLUME_SPIKE_RATIO": [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0],
}


def rows(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    current = rows(SIM / "current" / "prices.csv")
    change = rows(SIM / "marketchange" / "prices.csv")
    news = rows(SIM / "current" / "news_scored.csv") + rows(SIM / "marketchange" / "news_scored.csv")
    meta = json.loads((SIM / "marketchange" / "dataset.json").read_text())
    cases = [("sell", t, d, v) for d in ("2026-11-13", "2026-11-19") for t, v in meta["expected_verdict_if_sold"].items()]
    cases += [("buy", t, "2026-11-19", v) for t, v in meta["expected_verdict_if_bought"].items()]
    original = {k: getattr(sell_guard, k) for k in GRID}

    def score(params: dict) -> tuple[int, int]:
        for key, value in params.items():
            setattr(sell_guard, key, value)
        right = panic_right = panic_total = 0
        for action, ticker, day, expected in cases:
            got = sell_guard.evaluate_trade(action, ticker, current, change, news, day)["verdict"]
            right += got == expected
            if action == "sell" and expected == "panic_risk":
                panic_total += 1
                panic_right += got == "panic_risk"
        return right, panic_right

    names = list(GRID)
    results = {combo: score(dict(zip(names, combo))) for combo in itertools.product(*GRID.values())}
    for key, value in original.items():
        setattr(sell_guard, key, value)
    total = len(cases)
    perfect = {c for c, (r, _) in results.items() if r == total}
    print(f"{len(cases)} labelled cases, {len(results)} settings tried, {len(perfect)} classify every case correctly")

    # Robustness = how many of a setting's grid neighbours are also perfect.
    def neighbours(combo):
        for i, name in enumerate(names):
            idx = GRID[name].index(combo[i])
            for j in (idx - 1, idx + 1):
                if 0 <= j < len(GRID[name]):
                    yield combo[:i] + (GRID[name][j],) + combo[i + 1:]

    def robustness(combo) -> float:
        around = list(neighbours(combo))
        return sum(n in perfect for n in around) / len(around)

    for name in names:
        ok = sorted({c[names.index(name)] for c in perfect})
        print(f"  {name}: all-correct values seen = {ok}")
    best = max(perfect, key=lambda c: (robustness(c), -sum(abs(c[i] - original[n]) / (max(GRID[n]) - min(GRID[n])) for i, n in enumerate(names))))
    print("\nmost robust all-correct setting:", dict(zip(names, best)), f"(robustness {robustness(best):.0%})")
    now = tuple(original[n] for n in names)
    print("current setting:                ", dict(zip(names, now)), f"({results[now][0]}/{total} correct, robustness {robustness(now):.0%})" if now in results else "(off-grid)")
    print("\nPanic-sell recall at each margin (other thresholds at current values):")
    for margin in GRID["NET_DECISION_MARGIN"]:
        combo = (margin, original["DROP_THRESHOLD_PCT"], original["VOLUME_SPIKE_RATIO"])
        r, pr = results[combo]
        print(f"  margin {margin:.2f}: {r}/{total} correct, panic sells found {pr}/8")


if __name__ == "__main__":
    main()
