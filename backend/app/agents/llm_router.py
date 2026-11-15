"""Orchestrator routing: a language model decides what the person is asking.

One Amazon Bedrock call (Converse, tool choice forced) picks exactly one route and fills in its
details from natural language, so "is it smart to dump my Nvidia stock?" becomes a sell check
for NVDA without keyword rules:

* ``trade_check(action, ticker)``  run the pipeline: Intake, Market, Classifier, Explainer
* ``other_question()``             hand over to the rule-based router (FAQ, macro, accounts)
* ``say(text)``                    answer a greeting or an unclear message in one sentence

The model chooses the route only. It writes no figures: its one free-text route (``say``) may
contain no digits and no predictions, and every trade answer is produced by the pipeline.
When routing fails, the caller falls back to the rule-based router and says so in the trace.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

from app.agents import knowledge, trade_intent, trade_pipeline
from app.agents.explainer import PREDICTION
from app.agents.orchestrator import GlobalOrchestrator
from app.agents.orchestrator_text import DISCLAIMER
from app.domain.presets import PERSONAS
from app.i18n import normalize, pick
from app.services import bedrock
from app.services.errors import ExternalServiceError, ServiceConfigurationError

SYSTEM = """You route messages for PortfolioGuard AI, a simulation for fictional TFSA and RRSP investors.
Call exactly one tool:
- trade_check: the person is considering, in ANY wording, putting money into or taking money out of a specific
  stock, fund or asset: buy, sell, dump, ditch, unload, pick up, get into, load up, add to, cash out, hold off on.
  Gold means GLD. Give action buy or sell and the ticker symbol
  (NVDA, QQQ, SPY, GLD, ENB.TO, SHOP.TO, XIU.TO, FTS.TO, PG, ZST.TO, XBB.TO). "Is X a good idea?" about
  getting into X is a buy; about getting out of X is a sell.
- other_question: general questions that name no specific stock or asset to trade: accounts, TFSA, RRSP, risk,
  diversification, the economy, rates, recession, how investing works.
- say: a greeting or an unclear message. Write one short friendly sentence with NO digits and no predictions,
  inviting them to ask about a stock or the economy.
Never give advice. This is a simulation."""
FRENCH = "\nWrite any text in Canadian French."

TOOL_CONFIG = {
    "tools": [
        {"toolSpec": {"name": "trade_check", "description": "The person asks whether to buy or sell a specific stock or fund.", "inputSchema": {"json": {"type": "object", "properties": {"action": {"type": "string", "enum": ["buy", "sell"]}, "ticker": {"type": "string", "description": "Ticker symbol such as NVDA or ENB.TO"}}, "required": ["action", "ticker"]}}}},
        {"toolSpec": {"name": "other_question", "description": "Any question that is not about buying or selling a specific stock.", "inputSchema": {"json": {"type": "object", "properties": {}}}}},
        {"toolSpec": {"name": "say", "description": "Reply to a greeting or unclear message in one short sentence.", "inputSchema": {"json": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}}},
    ],
    "toolChoice": {"any": {}},
}


class RouterError(ExternalServiceError):
    """The routing model could not give a usable route."""


def enabled() -> bool:
    return os.getenv("LLM_ROUTING", "on").strip().lower() == "on"


def _route(message: str, lang: str, persona_id: Optional[str], live: bool, client: Any) -> Dict[str, Any]:
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise ServiceConfigurationError("BEDROCK_MODEL_ID is required")
    investor = f"The investor on screen is {PERSONAS[persona_id]['name']}." if persona_id in PERSONAS else "No investor is selected."
    system = f"{SYSTEM}\n{investor}" + (FRENCH if lang == "fr" else "")
    try:
        reply = (client or bedrock.client()).converse(
            modelId=model_id, system=[{"text": system}], messages=[{"role": "user", "content": [{"text": message}]}],
            toolConfig=TOOL_CONFIG, inferenceConfig={"maxTokens": 200, "temperature": 0.0},
        )["output"]["message"]
    except Exception as exc:  # throttling, access, timeouts, malformed responses
        raise RouterError(f"the routing model call failed: {type(exc).__name__}") from exc
    calls = [part["toolUse"] for part in reply.get("content", []) if "toolUse" in part]
    if len(calls) != 1 or calls[0]["name"] not in ("trade_check", "other_question", "say"):
        raise RouterError("the routing model did not pick exactly one known route")
    return {"name": calls[0]["name"], "args": calls[0].get("input") or {}}


def run(
    user_id: str,
    message: str,
    lang: str = "en",
    persona_id: Optional[str] = None,
    live: bool = False,
    client: Any = None,
    account_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """The chat reply, or None when the message belongs to the rule-based router (FAQ, macro, accounts)."""
    lang = normalize(lang)
    p = lambda en, fr: pick(lang, en, fr)  # noqa: E731
    route = _route(message, lang, persona_id, live, client)
    name, args = route["name"], route["args"]

    if name == "other_question":
        return None

    if name == "say":
        text = str(args.get("text", "")).strip()
        if not text or re.search(r"\d", text) or PREDICTION.search(text) or len(text) > 300:
            raise RouterError("the model's reply was empty or failed the checks")
        trace = [{"agent": "Global Orchestrator", "action": p("route the message with a language model: answer directly", "acheminer le message avec un modèle de langage : répondre directement")}]
        return GlobalOrchestrator._reply(text, trace, warnings=[p(DISCLAIMER, "Simulation seulement. Ce ne sont pas des conseils financiers.")], suggestions=knowledge.suggestions(lang))

    action = args.get("action")
    raw = str(args.get("ticker", "")).strip()
    ticker = trade_intent.resolve(raw) or (raw.upper() if re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", raw) else "")
    if action not in ("buy", "sell") or not ticker:
        raise RouterError("the routing model gave an invalid trade check")
    head = {"agent": "Global Orchestrator", "action": p(f"route the message with a language model: {action} check for {ticker}", f"acheminer le message avec un modèle de langage : vérification de {'vente' if action == 'sell' else 'achat'} pour {ticker}")}
    try:
        outcome = trade_pipeline.run(action, ticker, persona_id, account_type, live, lang, message=message, client=client, user_id=user_id)
    except LookupError:
        return GlobalOrchestrator._reply(
            p(f"I can check {'selling' if action == 'sell' else 'buying'} {ticker} once the live market is loaded. Refresh the market on the Holdings tab, then ask again.",
              f"Je peux vérifier {'la vente' if action == 'sell' else 'l’achat'} de {ticker} une fois le marché en direct chargé. Actualisez le marché dans l'onglet Titres, puis redemandez."),
            [head], warnings=[p(DISCLAIMER, "Simulation seulement. Ce ne sont pas des conseils financiers.")])
    except ValueError:
        return GlobalOrchestrator._reply(
            p(f"I don't have market data for {ticker} in this simulation.", f"Je n'ai pas de données de marché pour {ticker} dans cette simulation."),
            [head], warnings=[p(DISCLAIMER, "Simulation seulement. Ce ne sont pas des conseils financiers.")])
    reply = trade_pipeline.chat_reply(action, ticker, outcome, lang)
    reply["trace"] = [head] + outcome["trace"]
    return reply
