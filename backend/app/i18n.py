"""Language support for text the backend writes itself (chat replies, macro notes, explanations).

Structured analysis results (governance findings, trace steps, metric labels) are translated in
the frontend by id, so a language switch applies to them instantly. This module covers free text
that only the backend can produce.
"""

from __future__ import annotations

SUPPORTED = ("en", "fr")


def normalize(lang: str | None) -> str:
    """Return ``"fr"`` for any French locale, otherwise ``"en"``."""
    return "fr" if lang and lang.lower().startswith("fr") else "en"


def pick(lang: str | None, en: str, fr: str) -> str:
    return fr if normalize(lang) == "fr" else en


ACCOUNT_TYPE_FR = {
    "TFSA": "CELI",
    "RRSP": "REER",
    "FHSA": "CELIAPP",
    "Non-registered": "Non enregistré",
}
RISK_FR = {"Conservative": "Prudent", "Balanced": "Équilibré", "Growth": "Croissance"}
HORIZON_FR = {
    "short": "Court terme (3–5 ans)",
    "mid": "Moyen terme (8–12 ans)",
    "long": "Long terme (15 ans et plus)",
}
HORIZON_AGENT_FR = {
    "Short-Term Agent": "agent court terme",
    "Mid-Term Agent": "agent moyen terme",
    "Long-Term Agent": "agent long terme",
}
STRATEGY_FR = {
    "Preservation": "Préservation",
    "Bond": "Obligations",
    "Quality": "Qualité",
    "ESG": "ESG",
    "Dividend": "Dividendes",
    "Balanced Index": "Indice équilibré",
    "Growth": "Croissance",
    "Crypto": "Cryptomonnaies",
    "Momentum": "Momentum",
}


def account_type(lang: str | None, value: str) -> str:
    return ACCOUNT_TYPE_FR.get(value, value) if normalize(lang) == "fr" else value


def risk_label(lang: str | None, value: str) -> str:
    return RISK_FR.get(value, value) if normalize(lang) == "fr" else value


def horizon_agent(lang: str | None, value: str) -> str:
    return HORIZON_AGENT_FR.get(value, value) if normalize(lang) == "fr" else value


def strategies(lang: str | None, values: list[str]) -> list[str]:
    if normalize(lang) != "fr":
        return list(values)
    return [STRATEGY_FR.get(v, v) for v in values]


def account_name(lang: str | None, name: str) -> str:
    """'TFSA #1' becomes 'CELI #1' in French."""
    if normalize(lang) != "fr":
        return name
    for en, fr in ACCOUNT_TYPE_FR.items():
        if name.startswith(en):
            return fr + name[len(en):]
    return name


AGENT_FR = {
    "Macro Signal Agent": "agent de signaux macro",
    "Risk Agent": "agent de risque",
    "Bond Agent": "agent obligataire",
    "Investor Profile Agent": "agent de profil d'investisseur",
    "Crypto Agent": "agent cryptomonnaies",
    "ESG Agent": "agent ESG",
    "Balanced Index Agent": "agent d'indice équilibré",
    "Dividend Strategy Agent": "agent de stratégie de dividendes",
    "Growth Strategy Agent": "agent de stratégie de croissance",
    "Momentum Strategy Agent": "agent de stratégie momentum",
    "Technical Signal Agent": "agent de signaux techniques",
    "Capital Preservation Strategy Agent": "agent de préservation du capital",
    "Market Data Agent": "agent de données de marché",
    "Governance Agent": "agent de gouvernance",
    "Explainability Agent": "agent d'explicabilité",
    "Quality Agent": "agent de qualité",
    "Long-Term Horizon Agent": "agent d'horizon long terme",
}


def agent_names(lang: str | None, names: list[str]) -> str:
    """Comma-separated agent names in the requested language."""
    if normalize(lang) != "fr":
        return ", ".join(names)
    return ", ".join(AGENT_FR.get(name, name) for name in names)
