from __future__ import annotations

import math
import statistics
from datetime import date
from typing import Dict, Iterable, List, Mapping, Sequence

try:
    from .data_access import MarketDataset
except ImportError:  # Lambda CodeUri places modules at the runtime root.
    from data_access import MarketDataset


FORMULA_VERSION = "portfolio-risk-v1"
TRADING_DAYS_PER_YEAR = 252


def apply_shift(
    allocations: Mapping[str, float],
    from_strategy: str,
    to_strategy: str,
    amount: float,
) -> Dict[str, float]:
    proposed = dict(allocations)
    if from_strategy not in proposed or to_strategy not in proposed:
        raise ValueError("shift strategies must exist in strategy_allocations")
    if amount <= 0 or proposed[from_strategy] + 1e-12 < amount:
        raise ValueError("invalid strategy shift amount")
    proposed[from_strategy] = round(proposed[from_strategy] - amount, 12)
    proposed[to_strategy] = round(proposed[to_strategy] + amount, 12)
    if abs(sum(proposed.values()) - 1.0) > 1e-9:
        raise ValueError("proposed strategy allocations do not sum to 1")
    return proposed


def asset_weights(
    strategy_allocations: Mapping[str, float],
    strategy_holdings: Mapping[str, Mapping[str, float]],
) -> Dict[str, float]:
    weights: Dict[str, float] = {}
    for strategy, allocation in strategy_allocations.items():
        holdings = strategy_holdings.get(strategy)
        if holdings is None:
            raise ValueError(f"missing holdings for strategy: {strategy}")
        if abs(sum(holdings.values()) - 1.0) > 1e-9:
            raise ValueError(f"holdings for {strategy} do not sum to 1")
        for ticker, holding_weight in holdings.items():
            weights[ticker] = weights.get(ticker, 0.0) + allocation * holding_weight
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("asset weights do not sum to 1")
    return weights


def cad_price_series(
    dataset: MarketDataset,
    tickers: Iterable[str],
    start_date: date,
    end_date: date,
) -> Dict[str, Dict[date, float]]:
    result: Dict[str, Dict[date, float]] = {}
    for ticker in tickers:
        if ticker not in dataset.prices:
            raise ValueError(f"unsupported ticker: {ticker}")
        series: Dict[date, float] = {}
        for observation in dataset.prices[ticker]:
            if not (start_date <= observation.observation_date <= end_date):
                continue
            if observation.currency == "CAD":
                value = observation.adjusted_close
            elif observation.currency == "USD":
                value = observation.adjusted_close * dataset.prior_usdcad(
                    observation.observation_date
                )
            else:
                raise ValueError(
                    f"unsupported listing currency {observation.currency} for {ticker}"
                )
            series[observation.observation_date] = value
        if not series:
            raise ValueError(f"no prices for {ticker} in the requested window")
        result[ticker] = series
    return result


def common_dates(series: Mapping[str, Mapping[date, float]]) -> List[date]:
    date_sets = [set(values) for values in series.values()]
    if not date_sets:
        raise ValueError("portfolio has no assets")
    dates = sorted(set.intersection(*date_sets))
    if len(dates) < 60:
        raise ValueError("fewer than 60 common price observations in the requested window")
    return dates


def portfolio_returns(
    series: Mapping[str, Mapping[date, float]],
    dates: Sequence[date],
    weights: Mapping[str, float],
) -> List[float]:
    returns: List[float] = []
    for position in range(1, len(dates)):
        previous_date = dates[position - 1]
        current_date = dates[position]
        portfolio_return = 0.0
        for ticker, weight in weights.items():
            previous = series[ticker][previous_date]
            current = series[ticker][current_date]
            portfolio_return += weight * (current / previous - 1.0)
        returns.append(portfolio_return)
    return returns


def annualized_volatility(returns: Sequence[float]) -> float:
    if len(returns) < 2:
        raise ValueError("at least two returns are required")
    return statistics.stdev(returns) * math.sqrt(TRADING_DAYS_PER_YEAR)


def annualized_return(returns: Sequence[float]) -> float:
    growth = math.prod(1.0 + value for value in returns)
    return growth ** (TRADING_DAYS_PER_YEAR / len(returns)) - 1.0


def total_return(returns: Sequence[float]) -> float:
    return math.prod(1.0 + value for value in returns) - 1.0


def maximum_drawdown(returns: Sequence[float]) -> float:
    wealth = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        wealth *= 1.0 + value
        peak = max(peak, wealth)
        worst = min(worst, wealth / peak - 1.0)
    return worst


def concentration(weights: Mapping[str, float]) -> float:
    return sum(weight * weight for weight in weights.values())


def _metric(
    evidence_id: str,
    label: str,
    current: float,
    proposed: float,
    unit: str,
    source: str,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "label": label,
        "current": current,
        "proposed": proposed,
        "delta": proposed - current,
        "unit": unit,
        "source": source,
        "formula_version": FORMULA_VERSION,
    }
def _performance_series(
    dates: Sequence[date],
    current_returns: Sequence[float],
    proposed_returns: Sequence[float],
    max_points: int = 96,
) -> List[dict]:
    current_value = 1.0
    proposed_value = 1.0
    all_points = []
    for observation_date, current_return, proposed_return in zip(
        dates[1:], current_returns, proposed_returns
    ):
        current_value *= 1.0 + current_return
        proposed_value *= 1.0 + proposed_return
        all_points.append(
            {
                "date": observation_date.isoformat(),
                "current": current_value - 1.0,
                "proposed": proposed_value - 1.0,
            }
        )
    step = max(1, math.ceil(len(all_points) / max_points))
    sampled = all_points[::step]
    if sampled and sampled[-1] != all_points[-1]:
        sampled.append(all_points[-1])
    return sampled


def compare_strategy_shift(event: dict, dataset: MarketDataset) -> dict:
    allocations = {key: float(value) for key, value in event["strategy_allocations"].items()}
    shift = event["shift"]
    strategy_holdings = event["strategy_holdings"]
    start_date = date.fromisoformat(event["start_date"])
    end_date = date.fromisoformat(event["end_date"])

    if abs(sum(allocations.values()) - 1.0) > 1e-9:
        raise ValueError("strategy allocations must sum to 1")
    proposed_allocations = apply_shift(
        allocations,
        shift["from_strategy"],
        shift["to_strategy"],
        float(shift["amount"]),
    )
    current_weights = asset_weights(allocations, strategy_holdings)
    proposed_weights = asset_weights(proposed_allocations, strategy_holdings)
    tickers = sorted(set(current_weights) | set(proposed_weights))
    series = cad_price_series(dataset, tickers, start_date, end_date)
    dates = common_dates(series)
    current_returns = portfolio_returns(series, dates, current_weights)
    proposed_returns = portfolio_returns(series, dates, proposed_weights)

    source = "; ".join(dataset.sources) or "provided market dataset"
    metrics = [
        _metric(
            "metric.annualized_volatility",
            "Annualized volatility",
            annualized_volatility(current_returns),
            annualized_volatility(proposed_returns),
            "percent",
            source,
        ),
        _metric(
            "metric.maximum_drawdown",
            "Maximum drawdown",
            maximum_drawdown(current_returns),
            maximum_drawdown(proposed_returns),
            "percent",
            source,
        ),
        _metric(
            "metric.annualized_return",
            "Annualized historical return",
            annualized_return(current_returns),
            annualized_return(proposed_returns),
            "percent",
            source,
        ),
        _metric(
            "metric.total_return",
            "Total historical return",
            total_return(current_returns),
            total_return(proposed_returns),
            "percent",
            source,
        ),
        _metric(
            "metric.concentration_hhi",
            "Asset concentration (HHI)",
            concentration(current_weights),
            concentration(proposed_weights),
            "ratio",
            "strategy basket definitions",
        ),
    ]

    metric_map = {item["evidence_id"]: item for item in metrics}
    volatility_reduced = metric_map["metric.annualized_volatility"]["delta"] < 0
    drawdown_improved = metric_map["metric.maximum_drawdown"]["delta"] > 0
    if volatility_reduced and drawdown_improved:
        conclusion = "risk_reduced"
    elif not volatility_reduced and not drawdown_improved:
        conclusion = "risk_increased"
    else:
        conclusion = "mixed"

    return {
        "status": "ok",
        "operation": "compare_strategy_shift",
        "analysis_id": event["analysis_id"],
        "current_allocations": allocations,
        "proposed_allocations": proposed_allocations,
        "metrics": metrics,
        "conclusion": conclusion,
        "performance_series": _performance_series(
            dates, current_returns, proposed_returns
        ),
        "assumptions": [
            "Adjusted close is used for historical returns.",
            "USD listings are converted to CAD with the latest USD/CAD observation on or before each price date.",
            "Only dates shared by every holding are used.",
            "Portfolio weights are held constant through daily rebalancing.",
            f"The analysis window is {dates[0].isoformat()} through {dates[-1].isoformat()} ({len(dates)} common observations).",
        ],
        "limitations": [
            "Historical performance does not predict future results.",
            "The starter universe has survivorship and selection bias.",
            "Fees, taxes, contribution room, trading costs, and personal tax circumstances are excluded.",
            "Strategy baskets are fictional demonstration assumptions, not recommendations.",
        ],
        "data_sources": dataset.sources,
        "calculation_metadata": {
            "formula_version": FORMULA_VERSION,
            "base_currency": "CAD",
            "calendar_policy": "intersection",
            "rebalance_policy": "constant_weight_daily",
        },
    }
