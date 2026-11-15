"""Market, portfolio, trade-check and sentiment calculations.

Everything here is a request to the financial-tools Lambda (see ``engine``): the market data is
in S3 and the classification model is called from the Lambda. This module holds no data and no
market state. Whether the market has been "refreshed" is a flag the caller sends with each
request (``live``), so every user and every backend instance behaves the same.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.domain.presets import ACCOUNT_PRESETS, PERSONAS, STRATEGY_HOLDINGS
from app.services import engine
from app.services.errors import ExternalServiceError


def _invalid(exc: ExternalServiceError) -> ValueError | ExternalServiceError:
    """Bad input (an unknown ticker, say) is the caller's mistake, not an outage."""
    text = str(exc)
    return ValueError(text.split(": ", 1)[-1]) if "unknown ticker" in text or "no market-change data" in text else exc


def _call(operation: str, **payload: Any) -> Dict[str, Any]:
    try:
        return engine.run(operation, payload)
    except ExternalServiceError as exc:
        raise _invalid(exc) from exc


def _investor(persona_id: str, account_type: str | None) -> Dict[str, Any]:
    return {
        "persona_id": persona_id,
        "persona": PERSONAS[persona_id],
        "account_type": account_type,
        "account": ACCOUNT_PRESETS.get(account_type or ""),
        "strategy_holdings": STRATEGY_HOLDINGS,
    }


def market_status(live: bool = False) -> Dict[str, Any]:
    return _call("market_status", live=live)


def evaluate(action: str, ticker: str, live: bool = False) -> Dict[str, Any]:
    if not live:
        raise LookupError("refresh the live market before checking a trade")
    result = _call("trade_check", action=action, ticker=ticker, live=True)
    return {**result["trade_check"], "computed_by": result["computed_by"]}


def trade_check(
    action: str, ticker: str, persona_id: str | None = None, live: bool = False
) -> Dict[str, Any]:
    """Verdict plus, for an investor, their position and the latest headlines, in one Lambda call."""
    if not live:
        raise LookupError("refresh the live market before checking a trade")
    investor = _investor(persona_id, None) if persona_id in PERSONAS else {}
    result = _call("trade_check", action=action, ticker=ticker, live=True, **investor)
    return {
        "trade_check": {**result["trade_check"], "computed_by": result["computed_by"]},
        "position": result.get("position"),
        "headlines": result.get("headlines", []),
    }


def portfolio(persona_id: str, account_type: str | None = None, live: bool = False) -> Dict[str, Any]:
    result = _call("portfolio_snapshot", live=live, **_investor(persona_id, account_type))
    result.pop("status", None)
    result.pop("operation", None)
    return result


def sentiment_summary(ticker: str, half_life_days: float | None = None, live: bool = False) -> Dict[str, Any]:
    return _call("sentiment_summary", ticker=ticker, half_life_days=half_life_days, live=live)


def market_agent(ticker: str, live: bool = False) -> Dict[str, Any]:
    """Market agent step (Lambda): what changed between the two market snapshots."""
    if not live:
        raise LookupError("refresh the live market before checking a trade")
    result = _call("market_agent", ticker=ticker, live=True)
    return {**result["market"], "computed_by": result["computed_by"], "data_sources": result.get("data_sources", [])}


def classifier_agent(
    action: str, market: Dict[str, Any], risk_band: str | None = None, growth_style: bool = False,
    holding_pct: float | None = None,
) -> Dict[str, Any]:
    """Classifier agent step (Lambda): label the move and score it, from the Market agent's output.

    ``risk_band`` (low, mid, high; persona plus account rules) sets how big a move must be to count.
    """
    sent = {k: v for k, v in market.items() if k not in ("computed_by", "data_sources")}
    result = _call("classifier_agent", action=action, market=sent, risk_band=risk_band, growth_style=growth_style, holding_pct=holding_pct)
    return {
        "trade_check": {**result["trade_check"], "computed_by": result["computed_by"]},
        "headlines": result["headlines"],
    }


def investor_position(
    persona_id: str, ticker: str, action: str, account_type: str | None = None, live: bool = False
) -> Dict[str, Any]:
    """What the investor holds in ``ticker`` and a sample trade (Lambda)."""
    result = _call("investor_position", action=action, ticker=ticker, live=live, **_investor(persona_id, account_type))
    return result["position"]


def account_values(persona_id: str, account_types: list[str], live: bool = False) -> Dict[str, Dict[str, float]]:
    """The current value of each named account (Lambda): the one number every screen shows for it."""
    accounts = [{"account_type": t, "account": ACCOUNT_PRESETS[t]} for t in account_types if t in ACCOUNT_PRESETS]
    if not accounts:
        return {}
    result = _call(
        "account_values", live=live, accounts=accounts, persona_id=persona_id, persona=PERSONAS[persona_id],
        strategy_holdings=STRATEGY_HOLDINGS,
    )
    return result["values"]
