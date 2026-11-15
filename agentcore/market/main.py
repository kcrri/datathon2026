"""Market agent (AgentCore runtime): what changed between the two market snapshots.

Tool: ``compare_snapshots``. It invokes the financial-tools AWS Lambda, which reads the versioned
market data from S3 (before the trade, and after the refresh) and reports the price move, volume
and how many tracked tickers fell together, with citable evidence IDs.

The comparison depends on nothing else (not on who is asking), so this agent *preloads* it: on
``preload`` it compares every tracked ticker in parallel and keeps the results for a few minutes, so a
Buy or Sell click finds the answer already waiting. Cached results are the Lambda's own output for
the same inputs, never a guess.
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from common import envelope, run_agent  # noqa: E402

app = BedrockAgentCoreApp()

SYSTEM = """You are the Market agent of PortfolioGuard AI. Call compare_snapshots exactly once, then reply with the
single word done. Never state or alter any figure; the tool is the source of truth."""

CACHE_SECONDS = 600
_CACHE: dict = {}


def compare(ticker: str, live: bool):
    """The Market agent's answer for one ticker, from the preload cache when it is fresh. Returns (market, was_preloaded)."""
    from app.services import sell_guard_service

    key = (ticker, bool(live))
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1], True
    market = sell_guard_service.market_agent(ticker, bool(live))
    _CACHE[key] = (time.monotonic(), market)
    return market, False


def tracked_tickers() -> list:
    from app.domain.presets import STRATEGY_HOLDINGS

    return sorted({ticker for holdings in STRATEGY_HOLDINGS.values() for ticker in holdings})


def preload(p: dict) -> dict:
    """Compare every tracked ticker in parallel and keep the answers; hands the markets to the Classifier's preload."""
    live = bool(p.get("live"))
    if not live:
        raise LookupError("refresh the live market before preloading")
    tickers = [str(t).upper() for t in (p.get("tickers") or tracked_tickers())]

    def one(ticker: str):
        try:
            return ticker, compare(ticker, live)[0]
        except ValueError:  # no market data for this ticker
            return ticker, None

    with ThreadPoolExecutor(max_workers=6) as pool:
        markets = {t: m for t, m in pool.map(one, tickers) if m is not None}
    return {"preloaded": sorted(markets), "markets": markets}


def work(p: dict) -> dict:
    ticker = str(p["ticker"]).strip().upper()
    captured: dict = {}

    def compare_snapshots() -> dict:
        """Compare the market before and after the refresh for the ticker (AWS Lambda over S3, or already preloaded)."""
        market, hit = compare(ticker, bool(p.get("live")))
        captured["market"] = {**market, "_preloaded": hit}
        return captured["market"]

    return run_agent("market", SYSTEM, [compare_snapshots], f"Compare the snapshots for {ticker}.", captured, "market")


def serve(request: dict):
    """One request: ``{"action": ..., "payload": {...}}``. No action means this agent's default step."""
    payload = request.get("payload") or {}
    if request.get("action") == "preload":
        return preload(payload)
    return work(payload)


@app.entrypoint
def invoke(payload, context=None):
    return envelope(lambda: serve(payload or {}))


if __name__ == "__main__":
    app.run()
