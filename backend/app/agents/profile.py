"""Investor profile lookup and account recommendation helpers."""

import re
import unicodedata
from typing import Any, Dict, Optional
from app.domain.presets import PERSONAS
from app import i18n
from app.profiles import HORIZONS, PROFILES

ACCOUNT_BY_HORIZON = {
    "short": ("Non-registered", "Full flexibility and no contribution limit, so money is available when you need it."),
    "mid": ("TFSA", "Tax-free growth and withdrawals fit a medium horizon."),
    "long": ("RRSP", "Tax-deductible contributions and tax-deferred growth suit long-term and retirement goals."),
}


def get_persona(persona_id: str) -> dict:
    try:
        return PERSONAS[persona_id]
    except KeyError as exc:
        raise ValueError(f"unknown persona: {persona_id}") from exc


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().replace("\u2019", "'"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def parse_horizon(text: str) -> Optional[str]:
    lowered = _fold(text)
    if re.search(r"short|soon|near|court|bientot|proche", lowered):
        return "short"
    if re.search(r"\bmid|medium|moyen", lowered):
        return "mid"
    if re.search(r"long|retire|retraite", lowered):
        return "long"
    match = re.search(r"(\d+)\s*(?:years|yrs|year|ans|an)\b", lowered)
    if match:
        years = int(match.group(1))
        return "short" if years <= 5 else "mid" if years <= 12 else "long"
    return None


def parse_risk(text: str) -> Optional[str]:
    lowered = _fold(text)
    if re.search(r"low|conservative|safe|cautious|faible|prudent|securitaire", lowered):
        return "conservative"
    if re.search(r"moderate|balanced|medium risk|modere|equilibre", lowered):
        return "balanced"
    if re.search(r"high|aggressive|growth|eleve|agressif|croissance", lowered):
        return "growth"
    return None


REASONS_FR = {
    "Non-registered": "Flexibilité totale et aucune limite de cotisation : l'argent est disponible au moment où vous en avez besoin.",
    "TFSA": "La croissance et les retraits libres d'impôt conviennent à un horizon moyen.",
    "RRSP": "Les cotisations déductibles d'impôt et la croissance à imposition différée conviennent aux objectifs à long terme et à la retraite.",
    "FHSA": "Conçu pour l'achat d'une première propriété : cotisations déductibles et retraits libres d'impôt pour l'achat.",
}


def recommend(text: str, lang: str = "en") -> Dict[str, Any]:
    lowered = _fold(text)
    horizon = parse_horizon(lowered)
    if re.search(r"home|house|fhsa|maison|propriete|celiapp|hypotheque", lowered):
        account_type, reason = "FHSA", "Built for a first home purchase: deductible contributions and tax-free withdrawals for the home."
        horizon = horizon or "short"
    elif horizon:
        account_type, reason = ACCOUNT_BY_HORIZON[horizon]
    else:
        return {"needs": "horizon"}
    risk = parse_risk(lowered) or HORIZONS[horizon]["default_risk"]
    profile = PROFILES[risk]
    french = i18n.normalize(lang) == "fr"
    return {
        "account_type": account_type,  # stable key; the label below is localized
        "account_type_label": i18n.account_type(lang, account_type),
        "horizon": horizon,
        "horizon_label": i18n.HORIZON_FR[horizon] if french else HORIZONS[horizon]["label"],
        "risk": risk,
        "risk_label": i18n.risk_label(lang, profile["label"]),
        "persona": profile["persona"],
        "reason": REASONS_FR[account_type] if french else reason,
    }
