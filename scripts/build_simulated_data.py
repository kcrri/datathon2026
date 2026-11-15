#!/usr/bin/env python3
"""Build the two simulated datasets used by the panic-sell guard demo.

current/                  the investor's present situation: the last 60 trading
                           days of the starter prices (to 2026-11-12) plus calm,
                           SIMULATED news headlines.
marketchange/              what happens next: five SIMULATED trading days
                           (2026-11-13 to 2026-11-19) with price gaps, volume
                           spikes and negative headlines.

The market change mixes two stories so the guard has something to tell apart:
  * a market-wide scare (QQQ, NVDA, SHOP.TO, SPY): sharp drop, heavy volume, a
    partial rebound, generic market-wide headlines -> selling looks like panic;
  * a company-specific problem (ENB.TO): sharp drop, heavy volume, no rebound,
    headlines about the company itself -> selling is supported by the evidence.
Defensive holdings (ZST.TO, XBB.TO, GLD, PG, XIU.TO, FTS.TO) barely move.

Everything in marketchange/ is fictional. Output is deterministic.
"""
from __future__ import annotations

import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "hackathon_info" / "alphaforge_starter" / "prices_daily.csv"
OUT = ROOT / "data" / "simulated"
CURRENT = OUT / "current"
CHANGE = OUT / "marketchange"

CURRENT_DAYS = 60
SEED = 2026
TICKERS = [
    "QQQ", "NVDA", "SHOP.TO", "SPY",  # growth / market
    "XIU.TO", "ENB.TO", "FTS.TO", "PG",  # dividend / quality
    "ZST.TO", "XBB.TO", "GLD",  # preservation
]
CHANGE_DATES = ["2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"]

# Per-day close-to-close returns (%) and volume multipliers vs the 20-day median.
CHANGE_MOVES = {
    # market-wide scare: sharp drop, then a partial rebound
    "QQQ": ([-4.8, -2.1, 1.9, 1.4, 0.8], [3.0, 2.6, 1.8, 1.4, 1.2]),
    "NVDA": ([-8.5, -3.2, 2.6, 2.0, 1.1], [3.4, 2.9, 2.0, 1.6, 1.3]),
    "SHOP.TO": ([-6.9, -2.8, 2.2, 1.7, 0.9], [3.1, 2.5, 1.9, 1.5, 1.2]),
    "SPY": ([-3.4, -1.5, 1.4, 1.0, 0.6], [2.7, 2.3, 1.7, 1.4, 1.1]),
    # company-specific problem: the drop keeps going, no rebound
    "ENB.TO": ([-10.8, -3.6, -1.9, -0.7, -0.4], [4.2, 3.1, 2.2, 1.9, 1.7]),
    # defensives
    "XIU.TO": ([-1.6, -0.7, 0.8, 0.5, 0.3], [1.8, 1.5, 1.2, 1.1, 1.0]),
    "FTS.TO": ([-0.6, -0.2, 0.3, 0.2, 0.1], [1.2, 1.1, 1.0, 1.0, 1.0]),
    "PG": ([-0.8, -0.3, 0.4, 0.3, 0.2], [1.3, 1.2, 1.1, 1.0, 1.0]),
    "ZST.TO": ([0.0, 0.0, 0.0, 0.0, 0.0], [1.0, 1.0, 1.0, 1.0, 1.0]),
    "XBB.TO": ([0.2, 0.1, 0.0, 0.1, 0.0], [1.1, 1.1, 1.0, 1.0, 1.0]),
    "GLD": ([3.2, 1.6, 0.6, -0.2, 0.1], [2.4, 2.0, 1.5, 1.2, 1.1]),  # safe-haven rush
}

# What the guard should say if the investor BUYS (hype, falling knife, or a market-driven dip).
EXPECTED_BUY = {
    "QQQ": "dip_with_context",
    "NVDA": "dip_with_context",
    "SHOP.TO": "dip_with_context",
    "SPY": "dip_with_context",
    "ENB.TO": "falling_knife",
    "GLD": "chasing_risk",
    "XIU.TO": "no_signal",
    "FTS.TO": "no_signal",
    "PG": "no_signal",
    "ZST.TO": "no_signal",
    "XBB.TO": "no_signal",
}

# Ground truth for the demo and for testing the guard later.
EXPECTED = {
    "QQQ": "panic_risk",
    "NVDA": "panic_risk",
    "SHOP.TO": "panic_risk",
    "SPY": "panic_risk",
    "ENB.TO": "evidence_supported",
    "XIU.TO": "no_signal",
    "FTS.TO": "no_signal",
    "PG": "no_signal",
    "ZST.TO": "no_signal",
    "XBB.TO": "no_signal",
    "GLD": "no_signal",
}

# (date, ticker, scope, headline). All SIMULATED.
CURRENT_NEWS = [
    ("2026-10-22", "NVDA", "company", "Chipmaker posts steady data-centre demand in quarterly update"),
    ("2026-10-27", "QQQ", "market", "Technology shares edge higher as earnings season begins"),
    ("2026-11-02", "SHOP.TO", "company", "Online retailer platform reports stable merchant growth"),
    ("2026-11-03", "SPY", "market", "U.S. stocks end mixed ahead of central bank commentary"),
    ("2026-10-29", "ENB.TO", "company", "Pipeline operator reaffirms dividend and steady volumes"),
    ("2026-11-05", "XIU.TO", "market", "Canadian benchmark index holds near recent range"),
    ("2026-11-06", "FTS.TO", "company", "Utility completes routine rate filing with regulator"),
    ("2026-11-09", "PG", "company", "Household goods maker highlights stable consumer demand"),
    ("2026-11-10", "ZST.TO", "market", "Short-term bond yields little changed this week"),
    ("2026-11-11", "XBB.TO", "market", "Canadian bond market quiet as investors await inflation data"),
    ("2026-11-12", "GLD", "market", "Gold trades in a narrow range as dollar steadies"),
]

CHANGE_NEWS = [
    # market-wide scare: generic and fear-driven, no company-specific facts
    ("2026-11-13", "QQQ", "market", "Global equities slide as fears over interest rates resurface"),
    ("2026-11-13", "NVDA", "market", "Tech selloff deepens; investors dump high-valuation stocks"),
    ("2026-11-13", "SPY", "market", "Wall Street suffers worst day in months amid broad risk-off mood"),
    ("2026-11-13", "SHOP.TO", "market", "Canadian growth stocks fall in sympathy with global tech rout"),
    ("2026-11-16", "QQQ", "market", "Volatility index jumps as traders rush to cut risk"),
    ("2026-11-17", "NVDA", "market", "Analysts say selloff looks driven by positioning, not fundamentals"),
    ("2026-11-18", "SPY", "market", "Stocks recover part of losses as selling pressure eases"),
    # company-specific: concrete and about the company itself
    ("2026-11-13", "ENB.TO", "company", "Regulator orders pipeline operator to halt a segment pending safety review"),
    ("2026-11-16", "ENB.TO", "company", "Pipeline operator warns shutdown could reduce volumes and delay shipments"),
    ("2026-11-17", "ENB.TO", "company", "Rating agency places pipeline operator on review for possible downgrade"),
    ("2026-11-19", "ENB.TO", "company", "Pipeline operator says repairs will take longer than first expected"),
    # defensives
    ("2026-11-13", "GLD", "market", "Gold surges as investors rush into safe havens"),
    ("2026-11-16", "GLD", "market", "Record inflows into gold funds as demand for safe havens soars"),
    ("2026-11-13", "ZST.TO", "market", "Short-term bond ETFs hold steady during equity selloff"),
    ("2026-11-13", "PG", "company", "Consumer staples hold up better than the broader market"),
]

PRICE_HEADER = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume", "currency"]
NEWS_HEADER = ["date", "ticker", "scope", "headline", "source"]


def read_current() -> dict[str, list[dict]]:
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    with PRICES.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["ticker"] in TICKERS:
                by_ticker[row["ticker"]].append(row)
    return {ticker: rows[-CURRENT_DAYS:] for ticker, rows in by_ticker.items()}


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def build_change(current: dict[str, list[dict]]) -> list[list]:
    rng = random.Random(SEED)
    rows: list[list] = []
    for ticker in TICKERS:
        history = current[ticker]
        close = float(history[-1]["close"])
        currency = history[-1]["currency"]
        typical_volume = statistics.median(int(float(r["volume"])) for r in history[-20:])
        returns, multipliers = CHANGE_MOVES[ticker]
        for day, pct, mult in zip(CHANGE_DATES, returns, multipliers):
            open_price = close * (1 + pct / 200)  # opens roughly halfway to the close
            new_close = close * (1 + pct / 100)
            spread = abs(pct) / 200 + 0.002
            high = max(open_price, new_close) * (1 + spread * rng.uniform(0.3, 0.9))
            low = min(open_price, new_close) * (1 - spread * rng.uniform(0.3, 0.9))
            volume = int(typical_volume * mult * rng.uniform(0.95, 1.05))
            rows.append([
                day, ticker,
                f"{open_price:.6f}", f"{high:.6f}", f"{low:.6f}",
                f"{new_close:.6f}", f"{new_close:.6f}", volume, currency,
            ])
            close = new_close
    return rows


def main() -> None:
    current = read_current()
    for ticker in TICKERS:
        if len(current.get(ticker, [])) < CURRENT_DAYS:
            raise SystemExit(f"not enough price rows for {ticker}")

    current_rows = [
        [r[c] for c in PRICE_HEADER] for ticker in TICKERS for r in current[ticker]
    ]
    write_csv(CURRENT / "prices.csv", PRICE_HEADER, current_rows)
    write_csv(CURRENT / "news.csv", NEWS_HEADER, [[*n, "SIMULATED"] for n in CURRENT_NEWS])
    (CURRENT / "dataset.json").write_text(json.dumps({
        "dataset_id": "current-simulation-v1",
        "description": "The investor's present situation, before any market change.",
        "window": [current["QQQ"][0]["date"], current["QQQ"][-1]["date"]],
        "prices": "real starter prices; news is simulated",
    }, indent=2) + "\n")

    write_csv(CHANGE / "prices.csv", PRICE_HEADER, build_change(current))
    write_csv(CHANGE / "news.csv", NEWS_HEADER, [[*n, "SIMULATED"] for n in CHANGE_NEWS])
    (CHANGE / "dataset.json").write_text(json.dumps({
        "dataset_id": "market-change-simulation-v1",
        "description": "A simulated market change that follows the current simulation.",
        "window": [CHANGE_DATES[0], CHANGE_DATES[-1]],
        "simulated": True,
        "expected_verdict_if_sold": EXPECTED,
        "expected_verdict_if_bought": EXPECTED_BUY,
        "notes": "Fictional price moves and headlines for demonstration. Not real market data.",
    }, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
