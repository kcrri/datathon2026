"""Risk profiles, each based on a case persona."""

PROFILES = {
    "conservative": {
        "label": "Conservative",
        "persona": "Robert",
        "horizon": "short",
        "horizon_agent": "Short-Term Agent",
        "strategies": ["Preservation", "Bond", "Quality"],
    },
    "balanced": {
        "label": "Balanced",
        "persona": "Mateo",
        "horizon": "mid",
        "horizon_agent": "Mid-Term Agent",
        "strategies": ["ESG", "Dividend", "Balanced Index"],
    },
    "growth": {
        "label": "Growth",
        "persona": "Amira",
        "horizon": "long",
        "horizon_agent": "Long-Term Agent",
        "strategies": ["Growth", "Crypto", "Momentum"],
    },
}

HORIZONS = {
    "short": {"label": "Short term (3–5 yrs)", "default_risk": "conservative"},
    "mid": {"label": "Mid term (8–12 yrs)", "default_risk": "balanced"},
    "long": {"label": "Long term (15+ yrs)", "default_risk": "growth"},
}
