from __future__ import annotations

from typing import Dict


PERSONAS = {
    "amira": {
        "name": "Amira",
        "age": 26,
        "risk": "high",
        "horizon_years": "15+",
        "objective": "long-term capital growth with diversification",
        "preferences": ["AI and technology", "crypto", "diversification"],
        "starting_balance_cad": 15000,
        "starting_cash_cad": 2000,
        "default_allocations": {"growth": 0.55, "momentum": 0.25, "dividend": 0.10, "preservation": 0.10},
        # Amira is a risk-taker who holds only a few stocks, not a spread of baskets: NVDA is the
        # big bet (about 40% of the whole portfolio). Overrides the basket mix in every account.
        "concentrated_holdings": {"NVDA": 0.45, "SHOP.TO": 0.30, "QQQ": 0.25},
    },
    "mateo": {
        "name": "Mateo",
        "age": 41,
        "risk": "moderate",
        "horizon_years": "8-12",
        "objective": "balanced growth with stability",
        "preferences": ["ESG", "limited speculation", "diversification"],
        "starting_balance_cad": 60000,
        "starting_cash_cad": 5000,
        "default_allocations": {"growth": 0.30, "dividend": 0.35, "momentum": 0.10, "preservation": 0.25},
    },
    "robert": {
        "name": "Robert",
        "age": 59,
        "risk": "low-moderate",
        "horizon_years": "3-5",
        "objective": "capital preservation with some growth",
        "preferences": ["quality companies", "stability", "no crypto"],
        "starting_balance_cad": 150000,
        "starting_cash_cad": 10000,
        "default_allocations": {"preservation": 0.50, "dividend": 0.30, "growth": 0.15, "momentum": 0.05},
    },
}


STRATEGY_HOLDINGS: Dict[str, Dict[str, float]] = {
    "growth": {
        "QQQ": 0.35,
        "NVDA": 0.25,
        "SHOP.TO": 0.20,
        "SPY": 0.20,
    },
    "dividend": {
        "XIU.TO": 0.30,
        "ENB.TO": 0.25,
        "FTS.TO": 0.25,
        "PG": 0.20,
    },
    "momentum": {
        "QQQ": 0.40,
        "SPY": 0.30,
        "XIU.TO": 0.30,
    },
    "preservation": {
        "ZST.TO": 0.40,
        "XBB.TO": 0.30,
        "GLD": 0.20,
        "PG": 0.10,
    },
}


ACCOUNT_PRESETS: Dict[str, Dict[str, object]] = {
    "Non-registered": {
        "share": 0.50,
        "cash_share": 0.06,
        "allocations": {"growth": 0.45, "dividend": 0.25, "momentum": 0.20, "preservation": 0.10},
    },
    "TFSA": {
        "share": 0.30,
        "cash_share": 0.08,
        "allocations": {"growth": 0.50, "dividend": 0.20, "momentum": 0.20, "preservation": 0.10},
    },
    "RRSP": {
        "share": 0.20,
        "cash_share": 0.10,
        "allocations": {"growth": 0.25, "dividend": 0.35, "momentum": 0.10, "preservation": 0.30},
    },
}
