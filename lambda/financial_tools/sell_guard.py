"""Deterministic sell-guard signals: does the market data support selling a stock?

Pure functions over plain rows so they run the same locally, in tests and inside
AWS Lambda. Nothing here calls a model. News sentiment, when present, arrives as
a precomputed score per headline (from Comprehend, Bedrock or FinBERT) and is
reported as evidence, never used to invent a number.

Verdicts if the investor SELLS now:
  no_signal           the move is too small or volume too normal to matter
  panic_risk          sharp drop on heavy volume, driven by market-wide news
  evidence_supported  sharp drop on heavy volume, news about the company is negative
  mixed               sharp drop on heavy volume, but the causes are unclear

Verdicts if the investor BUYS now:
  no_signal           the move is too small or volume too normal to matter
  chasing_risk        sharp rise on heavy volume with upbeat headlines (buying the hype)
  falling_knife       sharp drop on heavy volume driven by negative company news
  dip_with_context    sharp drop on heavy volume driven by market-wide news
  mixed               sharp move on heavy volume, but the causes are unclear
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

try:  # packaged as a module (Lambda) or imported from the repo via sys.path
    from . import sentiment_tools
except ImportError:  # pragma: no cover
    import sentiment_tools

FORMULA_VERSION = "trade-guard-v4"

DROP_THRESHOLD_PCT = -3.0  # trough versus the last pre-event close
VOLUME_SPIKE_RATIO = 1.5  # event volume versus the typical (median) volume
BREADTH_PANIC_SHARE = 0.30  # share of tracked tickers that also dropped sharply
COMPANY_NEWS_SHARE = 0.50  # headlines are "about the company" only if MORE than this share is
RISE_THRESHOLD_PCT = 3.0  # peak versus the last pre-event close, for buy checks
# Scoring scales: the value at which each signal counts as "full strength".
FULL_VOLUME_EXCESS = 3.0  # volume at 1 + this many times typical = full intensity
FULL_REBOUND_PCT = 5.0  # a rebound this large means the drop was not lasting
FULL_RISE_PCT = 6.0  # a rally this large is full price momentum
NET_DECISION_MARGIN = 0.15  # fundamental minus emotion must beat this to pick a side
HYPE_THRESHOLD = 0.55  # hype score at or above this means chasing
TYPICAL_VOLUME_DAYS = 20
# Position size: selling a big share of the portfolio is a big decision, so a SELL of it must be backed
# by more evidence before it is called reasoned. From CONCENTRATION_START_PCT of the portfolio the
# company-driven minus market-driven balance is lowered by 0.10, rising to 0.25 at CONCENTRATION_FULL_PCT.
CONCENTRATION_START_PCT = 25.0
CONCENTRATION_FULL_PCT = 50.0
CONCENTRATION_MIN_BIAS = 0.10
CONCENTRATION_MAX_BIAS = 0.25


def concentration_bias(holding_pct: Optional[float]) -> float:
    """How far (a positive number) a SELL's net score is lowered because the position is a big part of the portfolio."""
    if not holding_pct or holding_pct < CONCENTRATION_START_PCT:
        return 0.0
    span = (min(holding_pct, CONCENTRATION_FULL_PCT) - CONCENTRATION_START_PCT) / (CONCENTRATION_FULL_PCT - CONCENTRATION_START_PCT)
    return round(CONCENTRATION_MIN_BIAS + (CONCENTRATION_MAX_BIAS - CONCENTRATION_MIN_BIAS) * span, 4)

# How big a move must be before it counts, by the investor's risk band. The band already
# includes the account rule (an RRSP lowers it one step), so persona and account both move
# these numbers. "mid" equals the defaults above, so a move with no investor behaves as before.
# A cautious investor is flagged on smaller moves; a high-risk, long-horizon one needs bigger ones.
# drop_pct / rise_pct: the move must be at least this big in absolute terms.
# sigma: and, when the ticker's own volatility is known, at least this many of its typical daily moves,
# so an ordinary day for a volatile stock is not flagged just because the percentage looks large.
# net_bias: added to (company-driven minus market-driven) before calling a SELL panic or reasoned. A short horizon
# and low risk tolerance leave less time to wait out a market-wide drop, so a cautious investor's sell is
# less often called pure fear (low +0.40, mid +0.20); a long-horizon, high-risk investor's is called as is.
# style_bias: extra, for a SELL of a growth-style holding (growth or momentum, not dividend or preservation).
# That holding does not match a short-horizon, capital-preservation plan, so selling it is consistent with the
# plan, not a reaction to fear (low +0.30, mid +0.10, high 0): Robert selling NVDA is not a panic sell.
RISK_BAND_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "low": {"drop_pct": -2.0, "rise_pct": 2.0, "volume_ratio": 1.3, "sigma": 1.5, "net_bias": 0.40, "style_bias": 0.30},
    "mid": {"drop_pct": DROP_THRESHOLD_PCT, "rise_pct": RISE_THRESHOLD_PCT, "volume_ratio": VOLUME_SPIKE_RATIO, "sigma": 2.0, "net_bias": 0.20, "style_bias": 0.10},
    "high": {"drop_pct": -4.0, "rise_pct": 4.0, "volume_ratio": 1.8, "sigma": 2.5, "net_bias": 0.0, "style_bias": 0.0},
}
VOLATILITY_DAYS = 60  # recent daily returns used to learn each ticker's normal swing


def thresholds_for(risk_band: Optional[str]) -> Dict[str, float]:
    """Gate values for a risk band; unknown or missing bands use the defaults (mid)."""
    return RISK_BAND_THRESHOLDS.get(risk_band or "mid", RISK_BAND_THRESHOLDS["mid"])


def _day(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def _by_ticker(prices: Iterable[Mapping[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in prices:
        grouped.setdefault(row["ticker"], []).append(
            {
                "date": _day(row["date"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
        )
    for rows in grouped.values():
        rows.sort(key=lambda r: r["date"])
    return grouped


def price_volume_signals(
    current_prices: Iterable[Mapping[str, Any]],
    change_prices: Iterable[Mapping[str, Any]],
    as_of: str | date,
) -> Dict[str, Dict[str, float]]:
    """Per-ticker drop, volume ratio and rebound using change rows up to ``as_of``."""
    cutoff = _day(as_of)
    current = _by_ticker(current_prices)
    change = _by_ticker(change_prices)
    signals: Dict[str, Dict[str, float]] = {}
    for ticker, history in current.items():
        window = [r for r in change.get(ticker, []) if r["date"] <= cutoff]
        if not window:
            continue
        reference_close = history[-1]["close"]
        typical_volume = statistics.median(r["volume"] for r in history[-TYPICAL_VOLUME_DAYS:])
        trough = min(r["close"] for r in window)
        peak = max(r["close"] for r in window)
        latest = window[-1]["close"]
        peak_volume = max(r["volume"] for r in window)
        closes = [r["close"] for r in history[-(VOLATILITY_DAYS + 1):]]
        returns = [(closes[i] / closes[i - 1] - 1) * 100 for i in range(1, len(closes))]
        daily_vol = statistics.pstdev(returns) if len(returns) >= 5 else 0.0
        signals[ticker] = {
            "daily_vol_pct": daily_vol,
            "drop_sigma": (trough / reference_close - 1) * 100 / daily_vol if daily_vol > 0 else None,
            "rise_sigma": (peak / reference_close - 1) * 100 / daily_vol if daily_vol > 0 else None,
            "drop_pct": (trough / reference_close - 1) * 100,
            "rise_pct": (peak / reference_close - 1) * 100,
            "latest_move_pct": (latest / reference_close - 1) * 100,
            "rebound_from_trough_pct": (latest / trough - 1) * 100,
            "volume_ratio": peak_volume / typical_volume,
            "days_observed": float(len(window)),
        }
    return signals


def news_signals(
    news: Iterable[Mapping[str, Any]], ticker: str, since: str | date, as_of: str | date
) -> Dict[str, float | None]:
    """Headline counts by scope and optional mean sentiment for one ticker.

    Only headlines from ``since`` (the first day of the market change) through
    ``as_of`` count, so calm background news does not dilute the event window.
    """
    start, cutoff = _day(since), _day(as_of)
    rows = [n for n in news if n["ticker"] == ticker and start <= _day(n["date"]) <= cutoff]
    company = sum(1 for n in rows if n.get("scope") == "company")
    scores = [float(n["sentiment"]) for n in rows if n.get("sentiment") not in (None, "")]
    return {
        "headline_count": float(len(rows)),
        "company_news_share": company / len(rows) if rows else 0.0,
        "mean_sentiment": statistics.fmean(scores) if scores else None,
    }


def breadth(signals: Mapping[str, Mapping[str, float]]) -> float:
    """Share of tracked tickers that fell at least as much as the drop threshold."""
    if not signals:
        return 0.0
    hit = sum(1 for s in signals.values() if s["drop_pct"] <= DROP_THRESHOLD_PCT)
    return hit / len(signals)


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_signals(
    rise_pct: float,
    volume_ratio: float,
    rebound_pct: float,
    company_news_share: float,
    market_breadth: float,
    sentiment: float | None,
) -> Dict[str, float]:
    """Turn the raw market signals into three 0..1 scores.

    fundamental  evidence that the move is about the company and will last:
                 0.5 * share of company headlines
                 0.3 * how negative the headline sentiment is
                 0.2 * how little the price has rebounded
    emotion      evidence that the move is market-driven or crowd-driven:
                 0.4 * share of headlines that are market-wide
                 0.3 * share of tracked tickers falling together
                 0.3 * how far volume is above normal
    hype         evidence of a rally fuelled by enthusiasm:
                 0.4 * how upbeat the headline sentiment is
                 0.3 * how far volume is above normal
                 0.3 * the size of the rise
    Missing sentiment counts as neutral (0), so the score never invents it.
    """
    s = 0.0 if sentiment is None else _clip(sentiment, -1.0, 1.0)
    intensity = _clip((volume_ratio - 1.0) / FULL_VOLUME_EXCESS)
    rebound = _clip(rebound_pct / FULL_REBOUND_PCT)
    return {
        "fundamental": 0.5 * company_news_share + 0.3 * _clip(-s) + 0.2 * (1.0 - rebound),
        "emotion": 0.4 * (1.0 - company_news_share) + 0.3 * market_breadth + 0.3 * intensity,
        "hype": 0.4 * _clip(s) + 0.3 * intensity + 0.3 * _clip(rise_pct / FULL_RISE_PCT),
    }


def decide(
    action: str,
    drop_pct: float,
    rise_pct: float,
    volume_ratio: float,
    scores: Mapping[str, float],
    risk_band: Optional[str] = None,
    drop_sigma: Optional[float] = None,
    rise_sigma: Optional[float] = None,
    growth_style: bool = False,
    holding_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """Categorise the action from the scores and report the score that decided it.

    Gate: nothing is flagged unless volume is at least the band's volume ratio times normal
    and the price moved at least the band's size against (drop) or with (rise) the investor.
    The band comes from the Intake agent (persona plus account rules): low 2%, mid 3%,
    high 4%. Without a band the mid values apply.

    When the ticker's own volatility is known (``drop_sigma`` / ``rise_sigma``, the move measured
    in its typical daily moves) the move must also be at least the band's number of typical daily
    moves (low 1.5, mid 2, high 2.5). A 3% drop is then unusual for a calm index fund and an
    ordinary day for a volatile stock.

    SELL  a drop is judged by net = fundamental - emotion:
            net >=  margin -> evidence_supported   (the data backs the concern)
            net <= -margin -> panic_risk           (market- or crowd-driven)
            otherwise      -> mixed
    BUY   a rise is judged by the hype score (>= HYPE_THRESHOLD -> chasing_risk);
          a drop uses the same net as a sell:
            net >=  margin -> falling_knife        (company trouble)
            net <= -margin -> dip_with_context     (market-driven dip)
            otherwise      -> mixed
    """
    gate = thresholds_for(risk_band)
    known = risk_band in RISK_BAND_THRESHOLDS
    # The profile only softens how a SELL is judged; buys keep the data's own balance.
    bias = (gate["net_bias"] + (gate["style_bias"] if growth_style else 0.0)) if known and action == "sell" else 0.0
    if action == "sell":
        bias -= concentration_bias(holding_pct)  # a big position needs more evidence before a sell is "reasoned"
    net = scores["fundamental"] - scores["emotion"] + bias
    heavy = volume_ratio >= gate["volume_ratio"]
    dropped = drop_pct <= gate["drop_pct"] and (drop_sigma is None or drop_sigma <= -gate["sigma"])
    rose = rise_pct >= gate["rise_pct"] and (rise_sigma is None or rise_sigma >= gate["sigma"]) and not dropped

    def split(high: str, low: str) -> str:
        return high if net >= NET_DECISION_MARGIN else low if net <= -NET_DECISION_MARGIN else "mixed"

    def balance_score() -> Dict[str, Any]:
        return {
            "name": "Company-driven vs market-driven",
            "value": round(50 + 50 * (net - bias), 1),  # the data's own balance, before the profile adjustment
            "low_label": "Market- or crowd-driven",
            "high_label": "Company-driven",
        }

    if not heavy:
        return {"verdict": "no_signal", "score": None}
    if action == "sell":
        if dropped:
            return {"verdict": split("evidence_supported", "panic_risk"), "score": balance_score()}
        return {"verdict": "no_signal", "score": None}
    if rose:
        verdict = "chasing_risk" if scores["hype"] >= HYPE_THRESHOLD else "mixed"
        return {
            "verdict": verdict,
            "score": {
                "name": "Hype",
                "value": round(100 * scores["hype"], 1),
                "low_label": "Calm",
                "high_label": "Hype",
            },
        }
    if dropped:
        return {"verdict": split("falling_knife", "dip_with_context"), "score": balance_score()}
    return {"verdict": "no_signal", "score": None}


def _evidence(
    ticker: str, key: str, label: str, value: float | None, unit: str, source: str
) -> Dict[str, Any]:
    return {
        "evidence_id": f"{ticker}:{key}",
        "label": label,
        "value": None if value is None else round(value, 4),
        "unit": unit,
        "source": source,
        "formula_version": FORMULA_VERSION,
    }


def market_change(
    ticker: str,
    current_prices: Sequence[Mapping[str, Any]],
    change_prices: Sequence[Mapping[str, Any]],
    as_of: str | date,
) -> Dict[str, Any]:
    """Market agent: compare the snapshot before the refresh with the one after it.

    Reports what changed for ``ticker`` (price move, volume, rebound) and how many of the tracked
    tickers fell together. Every figure is an evidence item with an ID the next agent can cite.
    """
    signals = price_volume_signals(current_prices, change_prices, as_of)
    if ticker not in signals:
        raise ValueError(f"no market-change data for {ticker} on or before {as_of}")
    own = signals[ticker]
    market_breadth = breadth(signals)
    market_drop = statistics.median(v["drop_pct"] for v in signals.values())
    market_rise = statistics.median(v["rise_pct"] for v in signals.values())
    return {
        "market_drop_pct": market_drop,
        "market_rise_pct": market_rise,
        "ticker": ticker,
        "as_of": _day(as_of).isoformat(),
        "since": min(_day(r["date"]) for r in change_prices).isoformat(),
        "signals": dict(own),
        "breadth": market_breadth,
        "tracked_tickers": len(signals),
        "tickers_falling_together": sum(1 for v in signals.values() if v["drop_pct"] <= DROP_THRESHOLD_PCT),
        "evidence": [
            _evidence(ticker, "drop", "Drop from last close to trough", own["drop_pct"], "percent", "prices"),
            _evidence(ticker, "rise", "Rise from last close to peak", own["rise_pct"], "percent", "prices"),
            _evidence(ticker, "volume", "Peak volume vs typical volume", own["volume_ratio"], "x", "prices"),
            _evidence(ticker, "rebound", "Rebound from trough", own["rebound_from_trough_pct"], "percent", "prices"),
            _evidence(ticker, "breadth", "Tracked tickers also down sharply", market_breadth * 100, "percent", "prices"),
            _evidence(ticker, "daily_move", "This ticker's typical daily move", own["daily_vol_pct"], "percent", "prices"),
            _evidence(ticker, "drop_size", "Drop in typical daily moves", own["drop_sigma"], "x", "prices"),
            _evidence(ticker, "market_drop", "Typical drop across all tracked tickers", market_drop, "percent", "prices"),
        ],
    }


def data_company_share(own: Mapping[str, Any], market: Mapping[str, Any]) -> float:
    """Share of the move that the market-wide move does not explain (0 = all market, 1 = all company).

    Used when a ticker has no headlines, so the "company or market" call still rests on the data:
    a stock that fell as much as the median tracked ticker is following the market; one that fell
    much more is moving on its own. Uses the larger of the ticker's drop and rise.
    """
    drop, rise = own["drop_pct"], own["rise_pct"]
    if abs(drop) >= abs(rise):
        own_move, market_move = drop, market.get("market_drop_pct", 0.0)
    else:
        own_move, market_move = rise, market.get("market_rise_pct", 0.0)
    if own_move == 0 or market_move * own_move <= 0:
        return 1.0 if own_move else 0.0
    return _clip(1.0 - market_move / own_move)


def classify_move(
    action: str,
    market: Mapping[str, Any],
    news: Sequence[Mapping[str, Any]],
    peers: Optional[Mapping[str, Sequence[str]]] = None,
    half_life_days: Optional[float] = None,
    risk_band: Optional[str] = None,
    growth_style: bool = False,
    holding_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """Classifier agent: label the move market-driven or company-driven and score it.

    Takes the Market agent's output, adds the news (headline sentiment pre-scored by the
    model), and returns the verdict with sentiment label and the fundamental, emotion and hype
    scores. Deterministic: the same inputs always give the same result.

    ``half_life_days`` (default off) makes older headlines count less. ``peers`` adds the
    cross-ticker sentiment as evidence; it never changes the verdict. ``risk_band`` (low, mid
    or high, from the Intake agent) sets how big a move has to be before it is flagged and how far a
    market-driven drop is excused for a cautious investor; ``growth_style`` says the ticker is a
    growth or momentum holding, which a low-risk plan does not expect to keep (a sell is then reasoned).
    ``holding_pct`` is the share of the portfolio the investor holds in this ticker: a SELL of a large position
    (25% and up) must clear a higher bar before it is called reasoned instead of panic.
    """
    if action not in ("buy", "sell"):
        raise ValueError("action must be buy or sell")
    ticker, as_of, since = market["ticker"], market["as_of"], market["since"]
    own, market_breadth = market["signals"], market["breadth"]
    story = news_signals(news, ticker, since, as_of)
    has_headlines = bool(story["headline_count"])
    company_share = (
        float(story["company_news_share"] or 0.0) if has_headlines else data_company_share(own, market)
    )
    window_rows = [
        n for n in news if n["ticker"] == ticker and _day(since) <= _day(n["date"]) <= _day(as_of)
    ]
    plain_sentiment = story["mean_sentiment"]
    decayed = sentiment_tools.weighted_sentiment(window_rows, as_of, half_life_days or sentiment_tools.DEFAULT_HALF_LIFE_DAYS)
    sentiment = decayed if half_life_days is not None else plain_sentiment
    categories = sentiment_tools.category_breakdown(window_rows)
    peer = (
        sentiment_tools.peer_sentiment(news, ticker, peers, since, as_of, half_life_days)
        if peers is not None
        else {"peer_sentiment": None, "peers_with_news": []}
    )
    market_rows = [
        n for n in news
        if n.get("scope") == "market" and _day(since) <= _day(n["date"]) <= _day(as_of)
    ]
    market_scores = [float(n["sentiment"]) for n in market_rows if n.get("sentiment") not in (None, "")]
    market_tone = statistics.fmean(market_scores) if market_scores else None
    scores = score_signals(
        own["rise_pct"],
        own["volume_ratio"],
        own["rebound_from_trough_pct"],
        company_share,
        market_breadth,
        sentiment,
    )
    decision = decide(
        action, own["drop_pct"], own["rise_pct"], own["volume_ratio"], scores, risk_band,
        drop_sigma=own.get("drop_sigma"), rise_sigma=own.get("rise_sigma"), growth_style=growth_style, holding_pct=holding_pct,
    )
    verdict = decision["verdict"]
    moved = max(abs(own["drop_pct"]), abs(own["rise_pct"]))
    sigma_now = own.get("drop_sigma") if abs(own["drop_pct"]) >= abs(own["rise_pct"]) else own.get("rise_sigma")
    net = scores["fundamental"] - scores["emotion"]
    gate = thresholds_for(risk_band)
    evidence = [
        *market["evidence"],
        _evidence(ticker, "drop_threshold", "Drop that counts for this investor", gate["drop_pct"], "percent", "profile"),
        _evidence(ticker, "volume_threshold", "Volume spike that counts for this investor", gate["volume_ratio"], "x", "profile"),
        _evidence(
            ticker, "company_news", "Share of the move that is company-specific", company_share * 100, "percent",
            "news" if has_headlines else "prices",
        ),
        _evidence(ticker, "sentiment", "Mean headline sentiment", sentiment, "score", "news"),
        _evidence(ticker, "market_news_count", "Market-wide headlines in the window", float(len(market_rows)), "count", "news"),
        _evidence(ticker, "market_news_tone", "Market-wide news tone", market_tone, "score", "news"),
        _evidence(ticker, "decayed_sentiment", "Recency-weighted sentiment", decayed, "score", "news"),
        _evidence(ticker, "peer_sentiment", "Related tickers' sentiment", peer["peer_sentiment"], "score", "news"),
        _evidence(ticker, "position_weight", "Share of the portfolio in this holding", holding_pct, "percent", "portfolio"),
        _evidence(ticker, "fundamental", "Company-driven score", scores["fundamental"] * 100, "points", "model"),
        _evidence(ticker, "emotion", "Market-driven score", scores["emotion"] * 100, "points", "model"),
        _evidence(ticker, "hype", "Hype score", scores["hype"] * 100, "points", "model"),
    ]
    return {
        "status": "ok",
        "operation": "evaluate_trade",
        "action": action,
        "ticker": ticker,
        "as_of": _day(as_of).isoformat(),
        "verdict": verdict,
        "move_size": {
            "move_pct": round(own["drop_pct"] if abs(own["drop_pct"]) >= abs(own["rise_pct"]) else own["rise_pct"], 2),
            "typical_daily_move_pct": round(own.get("daily_vol_pct") or 0.0, 2),
            "times_typical": None if sigma_now is None else round(abs(sigma_now), 1),
            "market_move_pct": round(market.get("market_drop_pct", 0.0), 2),
        },
        "severity": None if sigma_now is None else "mild" if abs(sigma_now) < 2.5 else "notable" if abs(sigma_now) < 4 else "severe",
        "significance": "unusual" if verdict != "no_signal" else "normal_swing" if moved else "none",
        "market_news": {
            "headlines": len(market_rows),
            "tone": None if market_tone is None else round(market_tone, 2),
            "label": None if market_tone is None else "upbeat" if market_tone >= 0.3 else "negative" if market_tone <= -0.3 else "neutral",
        },
        "company_share_basis": "headlines" if has_headlines else "price data",
        "risk_band": risk_band if risk_band in RISK_BAND_THRESHOLDS else None,
        "profile_adjustment": {
            "risk_band": risk_band if risk_band in RISK_BAND_THRESHOLDS else None,
            "net_bias": gate["net_bias"] if risk_band in RISK_BAND_THRESHOLDS and action == "sell" else 0.0,
            "growth_style": bool(growth_style),
            "holding_pct": holding_pct,
            "concentration_bias": concentration_bias(holding_pct) if action == "sell" else 0.0,
            "style_bias": gate["style_bias"] if risk_band in RISK_BAND_THRESHOLDS and growth_style and action == "sell" else 0.0,
        },
        "thresholds": dict(gate),
        "driver": "company" if net >= NET_DECISION_MARGIN else "market" if net <= -NET_DECISION_MARGIN else "mixed",
        "score": decision["score"],
        "sentiment": None if sentiment is None else round(sentiment, 2),
        "sentiment_label": None
        if sentiment is None
        else "upbeat" if sentiment >= 0.3 else "negative" if sentiment <= -0.3 else "neutral",
        "evidence": evidence,
        "headline_categories": categories,
        "peers_with_news": peer["peers_with_news"],
        "limitations": [
            "Verdicts describe how the market data looks; they are not advice or a forecast.",
            "Sentiment is missing until headlines are scored."
            if sentiment is None
            else "Sentiment and headline scope come from a model score and are shown as evidence.",
        ],
        "formula_version": FORMULA_VERSION,
    }


def evaluate_trade(
    action: str,
    ticker: str,
    current_prices: Sequence[Mapping[str, Any]],
    change_prices: Sequence[Mapping[str, Any]],
    news: Sequence[Mapping[str, Any]],
    as_of: str | date,
    peers: Optional[Mapping[str, Sequence[str]]] = None,
    half_life_days: Optional[float] = None,
) -> Dict[str, Any]:
    """Verdict and evidence for a buy or sell: the Market step followed by the Classifier step."""
    if action not in ("buy", "sell"):
        raise ValueError("action must be buy or sell")
    market = market_change(ticker, current_prices, change_prices, as_of)
    return classify_move(action, market, news, peers=peers, half_life_days=half_life_days)


def evaluate_sell(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Backward-compatible wrapper: ``evaluate_sell(ticker, ...)``."""
    return evaluate_trade("sell", *args, **kwargs)
