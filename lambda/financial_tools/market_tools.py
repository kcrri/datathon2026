"""Portfolio, trade-check and sentiment calculations over the market data.

Pure functions over the dict that ``market_store.load_market`` returns. Presets (the
investor profiles and strategy baskets) arrive in the request, so the Lambda holds no
product configuration. Nothing here calls a model.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

try:
    from . import sell_guard, sentiment_tools
except ImportError:  # Lambda CodeUri places modules at the runtime root.
    import sell_guard
    import sentiment_tools

SAMPLE_TRADE_SHARE = 0.10


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 2)


def market_status(data: Mapping[str, Any], live: bool) -> Dict[str, Any]:
    dates = set(data["dates"])
    return {
        "refreshed": live,
        "new_price_rows": len(data["change"]) if live else 0,
        "new_headlines": sum(1 for n in data["news"] if n["date"] in dates) if live else 0,
    }


def _as_of(data: Mapping[str, Any], live: bool) -> Optional[str]:
    return data["dates"][-1] if live else None


def holdings(strategy_holdings: Mapping[str, Mapping[str, float]], allocations: Mapping[str, float]) -> List[Dict[str, Any]]:
    """Each ticker's weight in an allocation across the strategy baskets."""
    weights: Dict[str, float] = {}
    for strategy, share in allocations.items():
        for ticker, weight in strategy_holdings.get(strategy, {}).items():
            weights[ticker] = weights.get(ticker, 0.0) + share * weight
    return [{"ticker": t, "weight": w} for t, w in sorted(weights.items(), key=lambda kv: -kv[1])]


def portfolio_snapshot(data: Mapping[str, Any], p: Mapping[str, Any]) -> Dict[str, Any]:
    """Fictional positions: shares are sized at the last pre-event close, then repriced."""
    live = bool(p.get("live"))
    as_of = _as_of(data, live)
    persona, account = p["persona"], p.get("account")
    balance = float(persona["starting_balance_cad"]) * (float(account["share"]) if account else 1.0)
    cash = balance * float(account["cash_share"]) if account else float(persona["starting_cash_cad"])
    allocations = account["allocations"] if account else persona["default_allocations"]
    investable = balance - cash  # the balance already includes the cash, so holdings are sized on the rest
    bought_at_reference = 0.0  # what the shares cost at the last pre-event close
    moves = sell_guard.price_volume_signals(data["current"], data["change"], as_of) if as_of else {}
    reference: Dict[str, float] = {}
    for row in data["current"]:
        reference[row["ticker"]] = float(row["close"])  # rows are date-ordered; the last one wins
    latest = dict(reference)
    if as_of:
        for row in data["change"]:
            if row["date"] <= as_of:
                latest[row["ticker"]] = float(row["close"])
    rows = []
    concentrated = persona.get("concentrated_holdings")  # a few big bets instead of the basket mix
    chosen = (
        [{"ticker": t, "weight": w} for t, w in sorted(concentrated.items(), key=lambda kv: -kv[1])]
        if concentrated
        else holdings(p["strategy_holdings"], allocations)
    )
    for item in chosen:
        ticker, weight = item["ticker"], item["weight"]
        price = latest[ticker]
        shares = round(investable * weight / reference[ticker], 2)
        bought_at_reference += shares * reference[ticker]
        rows.append(
            {
                "ticker": ticker,
                "weight": round(weight, 6),
                "shares": shares,
                "price": round(price, 2),
                "value_cad": round(shares * price, 2),
                "move_pct": round(moves.get(ticker, {}).get("latest_move_pct", 0.0), 2),
            }
        )
    invested = round(sum(r["value_cad"] for r in rows), 2)
    # Whole-cent share rounding leaves a few dollars unspent: that is cash. So before the refresh the
    # account is worth exactly its balance, and after it only the share prices move the total.
    cash = round(balance - bought_at_reference, 2)
    return {
        "persona_id": p["persona_id"],
        "account_type": p.get("account_type"),
        "starting_balance_cad": round(balance, 2),
        "refreshed": as_of is not None,
        "invested_cad": invested,
        "cash_cad": cash,
        "total_value_cad": round(invested + cash, 2),
        "holdings": rows,
        "note": "Fictional shares priced in each listing's own currency; FX is ignored.",
    }


def _last_price(data: Mapping[str, Any], ticker: str, as_of: Optional[str]) -> float:
    price = 0.0
    for row in data["current"]:
        if row["ticker"] == ticker:
            price = float(row["close"])
    if as_of:
        for row in data["change"]:
            if row["ticker"] == ticker and row["date"] <= as_of:
                price = float(row["close"])
    return price


def position(book: Mapping[str, Any], data: Mapping[str, Any], ticker: str, action: str, live: bool) -> Dict[str, Any]:
    """What the investor holds in ``ticker`` and a sample trade (10% of the holding, at least 1 share)."""
    row = next((h for h in book["holdings"] if h["ticker"] == ticker), None)
    shares = row["shares"] if row else 0.0
    price = row["price"] if row else round(_last_price(data, ticker, _as_of(data, live)), 2)
    qty = max(1.0, round(shares * SAMPLE_TRADE_SHARE))  # 10% of the holding, at least 1 share
    if action == "sell":
        qty = min(qty, shares)
    amount = round(qty * price, 2)
    total = book["total_value_cad"]
    cash_after = book["cash_cad"] + (amount if action == "sell" else -amount)
    return {
        "ticker": ticker,
        "action": action,
        "holds": shares > 0,
        "shares_held": shares,
        "price": price,
        "holding_pct": round(shares * price / total * 100, 1) if total else 0.0,
        "sample_qty": qty,
        "sample_amount_cad": amount,
        "portfolio_pct": round(amount / total * 100, 1) if total else 0.0,
        "cash_after_cad": round(cash_after, 2),
        "affordable": action == "sell" or cash_after >= 0,
    }


def sentiment_summary(data: Mapping[str, Any], p: Mapping[str, Any]) -> Dict[str, Any]:
    """Sentiment evidence for one ticker from the scored headlines (live window once refreshed)."""
    ticker = p["ticker"]
    live = bool(p.get("live"))
    half_life = p.get("half_life_days")
    if ticker not in {r["ticker"] for r in data["current"]}:
        raise ValueError(f"unknown ticker: {ticker}")
    news = data["news"]
    last_current = max(r["date"] for r in data["current"])
    as_of = _as_of(data, live) or max(n["date"] for n in news if n["date"] <= last_current)
    since = min(data["dates"]) if live else min(n["date"] for n in news)
    rows = [n for n in news if n["ticker"] == ticker and since <= n["date"] <= as_of]
    peer = sentiment_tools.peer_sentiment(news, ticker, data["peers"], since, as_of, half_life)
    return {
        "ticker": ticker,
        "as_of": as_of,
        "headline_count": len(rows),
        "mean_sentiment": _round(sentiment_tools.weighted_sentiment(rows, as_of)),
        "recency_weighted_sentiment": _round(
            sentiment_tools.weighted_sentiment(rows, as_of, half_life or sentiment_tools.DEFAULT_HALF_LIFE_DAYS)
        ),
        "peer_sentiment": _round(peer["peer_sentiment"]),
        "peers_with_news": peer["peers_with_news"],
        "categories": sentiment_tools.category_breakdown(rows),
        "headlines": [
            {"date": n["date"], "headline": n["headline"], "sentiment": n.get("sentiment") or None, "category": sentiment_tools.row_category(n)}
            for n in sorted(rows, key=lambda n: n["date"])
        ],
    }


def trade_check(data: Mapping[str, Any], p: Mapping[str, Any]) -> Dict[str, Any]:
    """Verdict and evidence, plus (when an investor is given) their position and the latest headlines."""
    live = bool(p.get("live"))
    if not live:
        raise ValueError("refresh the live market before checking a trade")
    action, ticker = p["action"], p["ticker"]
    result = sell_guard.evaluate_trade(
        action, ticker, data["current"], data["change"], data["news"], _as_of(data, live), peers=data["peers"]
    )
    out: Dict[str, Any] = {"trade_check": result, "position": None}
    if p.get("persona"):
        out["position"] = position(portfolio_snapshot(data, p), data, ticker, action, live)
    out["headlines"] = sentiment_summary(data, {"ticker": ticker, "live": live})["headlines"][-3:][::-1]
    return out


def market_agent(data: Mapping[str, Any], p: Mapping[str, Any]) -> Dict[str, Any]:
    """Market agent: what changed between the snapshot before the refresh and the one after it."""
    if not p.get("live"):
        raise ValueError("refresh the live market before checking a trade")
    return {"market": sell_guard.market_change(p["ticker"], data["current"], data["change"], _as_of(data, True))}


def classifier_agent(data: Mapping[str, Any], p: Mapping[str, Any]) -> Dict[str, Any]:
    """Classifier agent: label the move and score it, from the Market agent's output."""
    result = sell_guard.classify_move(
        p["action"], p["market"], data["news"], peers=data["peers"], risk_band=p.get("risk_band"),
        growth_style=bool(p.get("growth_style")), holding_pct=p.get("holding_pct"),
    )
    headlines = sentiment_summary(data, {"ticker": p["market"]["ticker"], "live": True})["headlines"][-3:][::-1]
    return {"trade_check": result, "headlines": headlines}


def investor_position(data: Mapping[str, Any], p: Mapping[str, Any]) -> Dict[str, Any]:
    """What the investor holds in the ticker and a sample trade."""
    book = portfolio_snapshot(data, p)
    return {"position": position(book, data, p["ticker"], p["action"], bool(p.get("live")))}


def account_values(data: Mapping[str, Any], p: Mapping[str, Any]) -> Dict[str, Any]:
    """The current value of each of an investor's accounts, in one call.

    This is THE number every screen shows for an account (the account list, the Accounts total and
    the Holdings total), so they cannot disagree: it is the same snapshot the Holdings panel uses.
    Before the market refresh a value equals the account's starting balance; after it, it moves
    with the prices.
    """
    values: Dict[str, Any] = {}
    for item in p["accounts"]:
        book = portfolio_snapshot(
            data,
            {
                "persona_id": p["persona_id"],
                "persona": p["persona"],
                "strategy_holdings": p["strategy_holdings"],
                "live": p.get("live"),
                "account_type": item["account_type"],
                "account": item["account"],
            },
        )
        values[item["account_type"]] = {
            "value_cad": book["total_value_cad"],
            "invested_cad": book["invested_cad"],
            "cash_cad": book["cash_cad"],
            "starting_balance_cad": book["starting_balance_cad"],
        }
    return {"values": values}
