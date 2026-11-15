"""Persona Fit: what a verdict may feel like for one fictional investor, and why.

Rule-based and deterministic (no model call). It reads the investor's risk level, horizon and
goal, whether the stock is growth-style or steady, and the guard's verdict, then returns a
stance ("fits your plan", "wait and watch", "be careful") with the reasons behind it. It
describes fit with the profile in a simulation; it is not advice.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app import i18n
from app.domain.presets import PERSONAS, STRATEGY_HOLDINGS

BAND = {"high": "high", "moderate": "moderate", "low-moderate": "low"}
RISK_LABEL = {
    "high": ("High", "Élevé"),
    "moderate": ("Moderate", "Modéré"),
    "low": ("Low to moderate", "Faible à modéré"),
}
GOAL_FR = {
    "amira": "croissance du capital à long terme avec diversification",
    "mateo": "croissance équilibrée avec stabilité",
    "robert": "préservation du capital avec un peu de croissance",
}

# (action, verdict) -> (stance, headline_en, headline_fr). Wording names the feeling; it never predicts.
HOW: Dict[tuple, tuple] = {
    ("sell", "panic_risk"): ("wait", "Fear can make a drop feel urgent. Take a moment before selling.", "La peur peut rendre une baisse urgente. Prenez un moment avant de vendre."),
    ("sell", "evidence_supported"): ("fits", "This sale looks like a reasoned decision, not a reaction to fear.", "Cette vente ressemble à une décision réfléchie, pas à une réaction de peur."),
    ("sell", "mixed"): ("wait", "The signals disagree, so check what you're feeling before you decide.", "Les signaux ne concordent pas : observez ce que vous ressentez avant de décider."),
    ("sell", "no_signal"): ("fits", "Nothing unusual is happening, so any urge to sell is worth questioning.", "Rien d'inhabituel : toute envie de vendre mérite d'être questionnée."),
    ("buy", "dip_with_context"): ("fits", "A drop can feel like a chance to jump in. This one looks market-wide, not about this company.", "Une baisse peut donner envie de sauter sur l'occasion. Celle-ci semble toucher tout le marché, pas cette entreprise."),
    ("buy", "chasing_risk"): ("careful", "Excitement and fear of missing out can pull you toward a buy like this.", "L'enthousiasme et la peur de passer à côté peuvent attirer vers un achat comme celui-ci."),
    ("buy", "falling_knife"): ("careful", "A falling price can feel like a bargain, but the news here is about the company itself.", "Un prix en baisse peut sembler une aubaine, mais ici les nouvelles concernent l'entreprise elle-même."),
    ("buy", "mixed"): ("wait", "The signals disagree, so check what you're feeling before you decide.", "Les signaux ne concordent pas : observez ce que vous ressentez avant de décider."),
    ("buy", "no_signal"): ("fits", "Nothing unusual is happening, so there is no strong pull either way.", "Rien d'inhabituel : rien ne pousse fortement dans un sens ou dans l'autre."),
}

# Stance tweaks by risk band: (action, verdict, band) -> stance
OVERRIDE = {
    ("buy", "chasing_risk", "high"): "wait",
}

# Extra reason by (action, verdict, band)
BAND_REASON: Dict[tuple, tuple] = {
    ("sell", "panic_risk", "high"): ("A long horizon means a short-term drop matters less to your goal, even if it feels alarming.", "Un horizon long signifie qu'une baisse à court terme compte moins pour votre objectif, même si elle semble alarmante."),
    ("sell", "panic_risk", "moderate"): ("You have time, so a sharp drop does not have to be answered right away.", "Vous avez du temps : une forte baisse n'exige pas de réponse immédiate."),
    ("sell", "panic_risk", "low"): ("Your horizon is shorter, so a drop can feel more urgent. If you need the money soon, that is a real reason; if not, it may be fear.", "Votre horizon est plus court, donc une baisse peut sembler plus urgente. Si vous avez bientôt besoin de l'argent, c'est une vraie raison; sinon, c'est peut-être la peur."),
    ("sell", "evidence_supported", "low"): ("Protecting what you have is your priority, so acting on a real concern is consistent.", "Protéger ce que vous avez est votre priorité : agir sur une inquiétude fondée est cohérent."),
    ("sell", "evidence_supported", "moderate"): ("You want balanced growth with stability, so acting on a real concern is consistent.", "Vous voulez une croissance équilibrée avec de la stabilité : agir sur une inquiétude fondée est cohérent."),
    ("sell", "evidence_supported", "high"): ("You can afford to act on a real concern and move on.", "Vous pouvez vous permettre d'agir sur une inquiétude fondée et de passer à autre chose."),
    ("buy", "dip_with_context", "moderate"): ("Buying in small steps can keep the urge to grab a bargain from sizing the trade for you.", "Acheter par petites étapes évite que l'envie de saisir une aubaine décide de la taille de l'achat."),
    ("buy", "dip_with_context", "high"): ("Your long-term growth goal is the reason to buy, not the urge to catch a bargain.", "Votre objectif de croissance à long terme est la raison d'acheter, pas l'envie de saisir une aubaine."),
    ("buy", "chasing_risk", "high"): ("Even long-term investors feel the pull of excitement; check that your plan, not the crowd, is driving this.", "Même les investisseurs à long terme ressentent l'attrait de l'enthousiasme; vérifiez que c'est votre plan, et non la foule, qui vous guide."),
    ("buy", "chasing_risk", "moderate"): ("Your plan limits speculation, and buying out of excitement is speculation.", "Votre plan limite la spéculation, et acheter par enthousiasme en est une."),
    ("buy", "chasing_risk", "low"): ("Your plan avoids speculation, and buying out of excitement is speculation.", "Votre plan évite la spéculation, et acheter par enthousiasme en est une."),
    ("buy", "falling_knife", "high"): ("A long horizon means you do not have to act on the first feeling of a bargain.", "Un horizon long signifie que vous n'avez pas à agir sur la première impression d'aubaine."),
}


def _custom_horizon_reason(band: str, text: str, lang: str) -> str:
    """For a horizon the investor described in their own words (for example "retire in 10 years")."""
    return {
        "high": i18n.pick(lang, f"With a horizon of {text}, short-term dips matter less to your goal.", f"Avec un horizon de {text}, les reculs à court terme comptent moins pour votre objectif."),
        "moderate": i18n.pick(lang, f"With a horizon of {text} you have time, but you also want stability.", f"Avec un horizon de {text}, vous avez du temps, mais vous voulez aussi de la stabilité."),
        "low": i18n.pick(lang, f"With a horizon of {text}, protecting what you have matters more than chasing growth.", f"Avec un horizon de {text}, protéger ce que vous avez compte plus que de courir après la croissance."),
    }[band]


def _horizon_reason(band: str, years: str, lang: str) -> str:
    return {
        "high": i18n.pick(lang, f"You're investing for {years} years, so short-term dips matter less to your goal.", f"Vous investissez pour {years} ans : les reculs à court terme comptent moins pour votre objectif."),
        "moderate": i18n.pick(lang, f"With {years} years ahead you have time, but you also want stability.", f"Avec {years} ans devant vous, vous avez du temps, mais vous voulez aussi de la stabilité."),
        "low": i18n.pick(lang, f"With only {years} years to go, protecting what you have matters more than chasing growth.", f"Avec seulement {years} ans devant vous, protéger ce que vous avez compte plus que de courir après la croissance."),
    }[band]


def is_growth_style(ticker: str) -> bool:
    groups = {s for s, holdings in STRATEGY_HOLDINGS.items() if ticker in holdings}
    return bool(groups & {"growth", "momentum"}) and not (groups & {"dividend", "preservation"})


CONCENTRATED_PCT = 25  # a holding this big (% of the portfolio) makes a trade a concentration risk

INTAKE_BAND = {"low": "low", "mid": "moderate", "high": "high"}


def fit(
    persona_id: str,
    action: str,
    ticker: str,
    verdict: str,
    position: Optional[Dict[str, Any]],
    lang: str = "en",
    risk_band: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Stance, headline and reasons for this investor. None when the persona is unknown."""
    persona = PERSONAS.get(persona_id)
    if not persona:
        return None
    lang = i18n.normalize(lang)
    p = lambda en, fr: i18n.pick(lang, en, fr)  # noqa: E731
    # The Intake agent's band (already adjusted for the account) wins over the persona preset.
    band = INTAKE_BAND[risk_band] if risk_band in INTAKE_BAND else BAND[persona["risk"]]
    years = persona["horizon_years"]
    goal = persona["objective"] if lang == "en" else GOAL_FR[persona_id]
    risk_label = RISK_LABEL[band][0 if lang == "en" else 1]
    profile = profile or {}
    if profile.get("goals"):
        goal = "; ".join(profile["goals"])
    header = {
        "id": persona_id,
        "name": profile.get("name") or persona["name"],
        "risk": risk_label,
        "horizon_years": years,
        "horizon_text": profile.get("horizon"),
        "goal": goal,
        "source": profile.get("source"),
    }

    if action == "sell" and position is not None and not position["holds"]:
        return {
            "persona": header,
            "stance": "wait",
            "headline": p(f"There is nothing to sell: you don't hold any {ticker}.", f"Rien à vendre : vous ne détenez aucun titre {ticker}."),
            "why": [],
        }

    stance, en, fr = HOW.get((action, verdict), ("wait", "Wait and watch.", "Attendre et observer."))
    stance = OVERRIDE.get((action, verdict, band), stance)
    horizon_reason = _custom_horizon_reason(band, profile["horizon"], lang) if profile.get("horizon") else _horizon_reason(band, years, lang)
    why: List[str] = [horizon_reason, p(f"Your goal is {goal}.", f"Votre objectif : {goal}.")]
    extra = BAND_REASON.get((action, verdict, band))
    if extra:
        why.append(p(*extra))
    headline = p(en, fr)
    if action == "buy" and is_growth_style(ticker) and band == "low" and stance == "fits":
        stance = "wait"
        headline = p(
            "The market data allows this buy, but a growth-style investment may not match your wish for stability. Check in with yourself first.",
            "Les données de marché permettent cet achat, mais un placement axé sur la croissance pourrait ne pas correspondre à votre désir de stabilité. Faites d'abord le point avec vous-même.",
        )
        why.append(p(f"{ticker} is a growth-style investment, and you prefer stability.", f"{ticker} est un placement axé sur la croissance, et vous préférez la stabilité."))
    if action == "sell" and is_growth_style(ticker) and band == "low":
        why.append(p(f"{ticker} is a growth-style holding, and a short horizon with capital preservation does not expect to keep one, so selling fits your plan.", f"{ticker} est un placement axé sur la croissance, et un horizon court avec préservation du capital ne prévoit pas d'en détenir : vendre est cohérent avec votre plan."))
    if action == "sell" and position is not None and position.get("holding_pct"):
        why.append(p(f"{ticker} is about {position['holding_pct']}% of your portfolio.", f"{ticker} représente environ {position['holding_pct']} % de votre portefeuille."))
    pct = (position or {}).get("holding_pct") or 0
    if action == "sell" and pct >= CONCENTRATED_PCT and (position or {}).get("holds"):
        # A big position is a big decision: selling it in a fear spike is the costliest panic sell.
        if verdict in ("panic_risk", "mixed", "no_signal"):
            stance = "careful"
            headline = p(
                f"{ticker} is about {pct}% of your portfolio. Selling a position this big because of fear is a panic sell with a large cost. Pause before you act.",
                f"{ticker} représente environ {pct} % de votre portefeuille. Vendre une position aussi importante par peur est une vente de panique au coût élevé. Faites une pause avant d'agir.",
            )
        why.append(p(
            f"Your portfolio is concentrated: one holding carries {pct}% of it, so this one decision moves your whole result. If you want less risk, trimming in small steps is easier to undo than selling it all.",
            f"Votre portefeuille est concentré : un seul titre en représente {pct} %, donc cette décision influence tout votre résultat. Pour réduire le risque, alléger par petites étapes est plus facile à corriger que tout vendre.",
        ))
    if action == "buy" and pct >= CONCENTRATED_PCT and (position or {}).get("holds"):
        stance = "careful" if stance == "fits" else stance
        why.append(p(
            f"{ticker} is already about {pct}% of your portfolio, so buying more adds to a risk you already carry.",
            f"{ticker} représente déjà environ {pct} % de votre portefeuille : en acheter plus ajoute à un risque que vous portez déjà.",
        ))
    return {"persona": header, "stance": stance, "headline": headline, "why": why}
