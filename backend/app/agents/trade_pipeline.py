"""The Orchestrator's route for "should I buy or sell X?": Intake, Market, Classifier, Explainer.

The agents run in order and pass evidence IDs along: the Market agent's figures become evidence
items, the Classifier adds its own, and the Explainer may cite only the Classifier's IDs. This
module does no calculation; Market and Classifier run in AWS Lambda over S3, the Explainer calls
Amazon Bedrock, and every step is recorded in the execution trace.

Raises LookupError when the market has not been refreshed and ValueError for a ticker with no data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services import investor_store
from app.services.errors import ExternalServiceError
from app.agents import classifier, explainer, intake, market_agent, persona_fit
from app.agents.orchestrator_text import DISCLAIMER
from app.domain.presets import PERSONAS
from app.i18n import normalize, pick
from app.services import sell_guard_service


def _where(computed_by: str, lang: str) -> str:
    return pick(lang, "AWS Lambda over S3" if computed_by == "aws-lambda" else "local files, not AWS", "AWS Lambda sur S3" if computed_by == "aws-lambda" else "fichiers locaux, pas AWS")


def run(
    action: str,
    ticker: str,
    persona_id: Optional[str] = None,
    account_type: Optional[str] = None,
    live: bool = False,
    lang: str = "en",
    message: Optional[str] = None,
    client: Any = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    lang = normalize(lang)
    ticker = ticker.strip().upper()
    trace: List[Dict[str, Any]] = []
    p = lambda en, fr: pick(lang, en, fr)  # noqa: E731

    # 0. The investor: the request's choice wins and is saved to S3; with none, the saved one is read from S3.
    stored_note = ""
    stored = None
    if user_id:
        try:
            stored = investor_store.load(user_id)
            if persona_id is None and stored:
                persona_id, account_type = stored["persona_id"], account_type or stored["account_type"]
                stored_note = p("; investor read from S3", "; investisseur lu depuis S3")
            elif persona_id in PERSONAS and (not stored or stored["persona_id"] != persona_id or (account_type and stored["account_type"] != account_type)):
                investor_store.save(user_id, persona_id, account_type or (stored["account_type"] if stored and stored["persona_id"] == persona_id else None))
                stored_note = p("; investor saved to S3", "; investisseur enregistré dans S3")
        except (ExternalServiceError, ValueError):
            stored_note = p("; S3 investor store unavailable", "; magasin d'investisseur S3 indisponible")

    # 1. Intake: who is asking, as a low, mid or high risk persona (account rules applied)
    who = intake.run(persona_id, account_type, message, lang, client=client)
    if who["risk_band"]:
        detail = p(f"read {who['persona_name'] or 'the described investor'} as a {who['risk_band']}-risk persona", f"lire {who['persona_name'] or "l'investisseur décrit"} comme un profil à risque {who['risk_band']}")
        if who["account_rule"]:
            detail += f"; {who['account_rule']}"
    else:
        detail = p("no investor selected, so the check is not personalised", "aucun investisseur sélectionné : la vérification n'est pas personnalisée")
    trace.append({"agent": "Intake", "action": detail + stored_note})

    # 2. Market: what changed between the two snapshots (AWS Lambda over S3)
    market = market_agent.run(ticker, live)
    trace.append({"agent": "Market", "action": p(
        f"compare the market before and after the refresh ({_where(market['computed_by'], lang)}): {market['tickers_falling_together']} of {market['tracked_tickers']} tracked tickers fell together",
        f"comparer le marché avant et après l'actualisation ({_where(market['computed_by'], lang)}) : {market['tickers_falling_together']} des {market['tracked_tickers']} titres suivis ont baissé ensemble")})

    position = None
    if persona_id in PERSONAS:
        position = sell_guard_service.investor_position(persona_id, ticker, action, account_type, live)
    # How much of the portfolio this holding is: a big position raises the bar for calling a sell reasoned
    holding_pct = position["holding_pct"] if position and action == "sell" and position["holds"] else None

    # 3. Classifier: market-driven or company-driven, with scores (AWS Lambda; headlines pre-scored by Bedrock)
    classified = classifier.run(action, market, who["risk_band"], persona_fit.is_growth_style(ticker), holding_pct)
    result = classified["trade_check"]
    trace.append({"agent": "Classifier", "action": p(
        f"label the move {result['driver']}-driven and score it, citing {len(result['evidence'])} evidence items ({_where(result['computed_by'], lang)})",
        f"qualifier le mouvement comme lié à « {result['driver']} » et le noter, en citant {len(result['evidence'])} éléments de preuve ({_where(result['computed_by'], lang)})")})

    fit = None
    if persona_id in PERSONAS:
        profile = stored.get("profile") if stored and stored.get("persona_id") == persona_id else None
        fit = persona_fit.fit(persona_id, action, ticker, result["verdict"], position, lang, risk_band=who["risk_band"], profile=profile)

    # 4. Explainer: the pop-up warning, then the full detail, citing only the Classifier's evidence IDs
    explanation: Optional[Dict[str, Any]] = None
    if explainer.enabled():
        try:
            explanation = explainer.explain(action, result, fit, who, lang, client=client)
            note = p("write the pop-up warning and the chat detail with Amazon Bedrock, citing only the Classifier's evidence IDs", "rédiger l'avertissement et le détail avec Amazon Bedrock, en ne citant que les identifiants de preuve du classificateur")
            if explanation is None:
                note = p("the model's text was rejected by the checks, so the fixed wording is used", "le texte du modèle a été refusé par les contrôles : le texte fixe est utilisé")
        except Exception as exc:  # the card still works without generated text
            note = p(f"the explainer was unavailable ({type(exc).__name__}), so the fixed wording is used", f"l'explicateur était indisponible ({type(exc).__name__}) : le texte fixe est utilisé")
    else:
        note = p("fixed wording (the explainer model is switched off)", "texte fixe (le modèle explicateur est désactivé)")
    trace.append({"agent": "Explainer", "action": note})

    result = {**result, "explanation": explanation}
    if fit:
        result["persona_fit"] = fit
    return {
        "trade_check": result,
        "position": position,
        "headlines": classified["headlines"],
        "persona_fit": fit,
        "explanation": explanation,
        "intake": who,
        "trace": trace,
    }


def chat_reply(action: str, ticker: str, outcome: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """The chat message for a finished pipeline (shape shared with the rule-based replies)."""
    lang = normalize(lang)
    explanation = outcome["explanation"]
    verb = pick(lang, "selling" if action == "sell" else "buying", "la vente" if action == "sell" else "l'achat")
    answer = explanation["detail"] if explanation else pick(lang, f"Here is what the live data says about **{verb} {ticker}**.", f"Voici ce que disent les données en direct sur **{verb} {ticker}**.")
    other = "buy" if action == "sell" else "sell"
    return {
        "answer": answer,
        "trace": outcome["trace"],
        "metrics": {},
        "sources": [pick(lang, "Simulated market data and scored headlines", "Données de marché simulées et titres évalués")],
        "warnings": [pick(lang, DISCLAIMER, "Simulation seulement. Ce ne sont pas des conseils financiers.")],
        "proposal": None,
        "suggestions": [pick(lang, f"Should I {other} {ticker}?", f"Devrais-je {'acheter' if other == 'buy' else 'vendre'} {ticker} ?")],
        "trade_check": outcome["trade_check"],
        "position": outcome["position"],
        "headlines": outcome["headlines"],
        "persona_fit": outcome["persona_fit"],
    }
