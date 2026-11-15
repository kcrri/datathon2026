"""Classifier agent (AgentCore runtime): market-driven or company-driven, with a sentiment label.

Tool: ``classify_move``. Deterministic code in the financial-tools AWS Lambda scores the Market
agent's change and the headlines (their sentiment pre-scored by Bedrock) into fundamental, emotion
and hype scores and a verdict. The investor's risk band and whether the ticker is a growth holding
change how big a move must be and how a sell is judged: Robert selling NVDA is not a panic sell.

It also owns ``sentiment_ask`` (a question about a ticker's news tone) and *preloads*: the verdict for a
ticker depends only on the market change and the three risk bands, not on who is asking, so on
``preload`` it classifies every ticker, buy and sell, for low, mid and high in parallel and keeps the
answers, so a click only needs to look up the band. Cached results are the Lambda's own output for the
same inputs.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from common import envelope, owned, run_agent  # noqa: E402

app = BedrockAgentCoreApp()

SYSTEM = """You are the Classifier agent of PortfolioGuard AI. Call classify_move exactly once, then reply with the
single word done. Never change the verdict or any score; the tool is the source of truth."""

OWNED = {"sentiment_ask"}  # run directly, without a model loop
BANDS = ("low", "mid", "high")
CACHE_SECONDS = 600
_CACHE: dict = {}


def classify(action: str, ticker: str, market: dict, risk_band, growth: bool = None, holding_pct: float = None):
    """The Classifier's answer, from the preload cache when the exact same inputs were already classified."""
    from app.agents import persona_fit
    from app.services import sell_guard_service

    market = {k: v for k, v in market.items() if not k.startswith("_")}
    growth = persona_fit.is_growth_style(ticker) if growth is None else growth
    key = hashlib.sha256(json.dumps([action, market, risk_band, growth, holding_pct], sort_keys=True, default=str).encode()).hexdigest()
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1], True
    result = sell_guard_service.classifier_agent(action, market, risk_band, growth, holding_pct)
    _CACHE[key] = (time.monotonic(), result)
    return result, False


def holding_share(p: dict, action: str, ticker: str):
    """The share (%) of the investor's portfolio held in this ticker, for a sell; None when no investor is chosen or it is not a sell."""
    from app.domain.presets import PERSONAS
    from app.services import sell_guard_service

    if action != "sell" or p.get("persona") not in PERSONAS:
        return None
    try:
        position = sell_guard_service.investor_position(p["persona"], ticker, action, p.get("account_type"), True)
    except Exception:  # the check still works without the position size
        return None
    return position.get("holding_pct") if position.get("holds") else None


def preload(p: dict) -> dict:
    """Classify every preloaded market, both actions, all three risk bands, in parallel."""
    jobs = [(a, t, m, b) for t, m in (p.get("markets") or {}).items() for a in ("buy", "sell") for b in BANDS]

    def one(job):
        action, ticker, market, band = job
        try:
            return classify(action, ticker, market, band)[0] is not None
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        done = sum(1 for ok in pool.map(one, jobs) if ok)
    return {"preloaded": done, "of": len(jobs)}


def work(p: dict) -> dict:
    action, ticker = p["action"], str(p["ticker"]).strip().upper()
    captured: dict = {}

    def classify_move() -> dict:
        """Label the move and score it from the Market agent's output (AWS Lambda, or already preloaded; no model decides)."""
        result, hit = classify(action, ticker, p["market"], p.get("risk_band"), holding_pct=holding_share(p, action, ticker))
        captured["classified"] = {**result, "_preloaded": hit}
        return captured["classified"]

    return run_agent("classifier", SYSTEM, [classify_move], f"Classify the {action} of {ticker}.", captured, "classified")


def serve(request: dict):
    """One request: ``{"action": ..., "payload": {...}}``. No action means this agent's default step."""
    action, payload = request.get("action"), request.get("payload") or {}
    if action == "preload":
        return preload(payload)
    if action in OWNED:
        return owned(action, payload)
    return work(payload)


@app.entrypoint
def invoke(payload, context=None):
    return envelope(lambda: serve(payload or {}))


if __name__ == "__main__":
    app.run()
