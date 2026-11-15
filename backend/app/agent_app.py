"""The agents' entry point: one function that runs an action and returns JSON.

This is what runs inside the AgentCore runtime (see ``agentcore/main.py``), so the orchestrator
and every agent execute in the AWS account. The local backend only forwards requests to it
(``app.services.agent_runtime``). ``AGENTS=local`` runs the same function in-process, for tests
and offline work. Nothing here keeps market state: the caller sends ``live`` with each request.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional

from pydantic import ValidationError

from app.agents import llm_router, trade_pipeline
from app.agents.orchestrator import GlobalOrchestrator
from app.agents.signals import sentiment as sentiment_agent
from app.domain.models import AnalysisRequest
from app.domain.presets import PERSONAS
from app.i18n import normalize
from app.services import investor_store, sell_guard_service
from app.services.errors import ExternalServiceError, ServiceConfigurationError

orchestrator = GlobalOrchestrator()


class AgentError(Exception):
    """A failure the caller should see, with the HTTP status the API maps it to."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _chat(p: Dict[str, Any]) -> Dict[str, Any]:
    if p.get("persona_id"):
        request = AnalysisRequest(
            persona_id=p["persona_id"], question=p["message"], language=normalize(p.get("lang", "en"))
        )
        return orchestrator.run(request).model_dump(mode="json")
    user, message, lang = p.get("user_id", "demo"), p["message"], p.get("lang", "en")
    persona, live = p.get("holdings_persona"), bool(p.get("live"))
    reply = None
    # Account creation stays a rule-based, user-approved flow. Everything else is routed by a
    # language model (Orchestrator); FAQ and macro questions are then answered by the rule-based
    # router, and a routing failure falls back to it too, noted in the trace.
    if llm_router.enabled() and not orchestrator._is_create_intent(message):
        try:
            reply = llm_router.run(user, message, lang, persona, live)
        except (ExternalServiceError, ServiceConfigurationError) as exc:
            reply = orchestrator.chat(user, message, lang, persona, live)
            reply["trace"].insert(1, {"agent": "Global Orchestrator", "action": (f"routage par modèle indisponible ({exc}) : routeur à règles utilisé" if normalize(lang) == "fr" else f"model routing unavailable ({exc}): used the rule-based router")})
    if reply is None:
        reply = orchestrator.chat(user, message, lang, persona, live)
    runtime = os.getenv("AGENT_RUNTIME_NAME")
    if runtime:  # say where the agents ran, as the first step of the visible trace
        fr = normalize(p.get("lang", "en")) == "fr"
        reply["trace"].insert(
            0,
            {
                "agent": "AgentCore Runtime",
                "action": f"exécuter les agents dans le compte AWS ({runtime})" if fr else f"run the agents in the AWS account ({runtime})",
            },
        )
    return reply


def _analysis(p: Dict[str, Any]) -> Dict[str, Any]:
    return orchestrator.run(AnalysisRequest.model_validate(p)).model_dump(mode="json")


def _accounts(p: Dict[str, Any]) -> Any:
    """The investor's accounts, each with ONE current value (``value_cad``) from the Lambda.

    Every screen shows that value, so the account list, the Accounts total and the Holdings
    total cannot disagree. Accounts the Lambda cannot price (a new, empty account) keep their
    stored balance, and if the Lambda is unreachable the list still loads with stored balances.
    """
    from app import store

    persona_id, live = p.get("persona_id"), bool(p.get("live"))
    accounts = [dict(a) for a in store.accounts(p.get("user_id", "demo")) if persona_id is None or a.get("persona_id") == persona_id]
    priced: Dict[str, Dict[str, float]] = {}
    if persona_id in PERSONAS:
        try:
            priced = sell_guard_service.account_values(persona_id, sorted({a["type"] for a in accounts if a.get("persona_id") == persona_id}), live)
        except ExternalServiceError:
            priced = {}
    for account in accounts:
        value = priced.get(account["type"]) if account.get("persona_id") == persona_id else None
        account["value_cad"] = value["value_cad"] if value else float(account.get("balance") or 0.0)
        account["invested_cad"] = value["invested_cad"] if value else float(account.get("balance") or 0.0)
        account["cash_cad"] = value["cash_cad"] if value else 0.0
        account["value_source"] = "market" if value else "stored balance"
    return accounts


def _delete_account(p: Dict[str, Any]) -> Dict[str, bool]:
    from app import store

    if not store.delete_account(p.get("user_id", "demo"), p["account_id"]):
        raise AgentError(404, f"Account {p['account_id']} not found")
    return {"deleted": True}


def _trade_check(p: Dict[str, Any]) -> Dict[str, Any]:
    """The Holdings pop-up and card: Intake, Market, Classifier and Explainer, run in order."""
    try:
        outcome = trade_pipeline.run(
            p["action"], p["ticker"], p.get("persona"), p.get("account_type"), bool(p.get("live")), p.get("lang", "en"),
            user_id=p.get("user_id"),
        )
    except LookupError as exc:
        raise AgentError(409, str(exc)) from exc
    return {**outcome["trade_check"], "trace": outcome["trace"], "intake": outcome["intake"]}


def _sentiment_ask(p: Dict[str, Any]) -> Dict[str, Any]:
    return sentiment_agent.ask(p["question"], p.get("language", "en"), live=bool(p.get("live")))


def _runtime(_: Dict[str, Any]) -> Dict[str, Any]:
    return {"agents": "agentcore" if os.getenv("AGENT_RUNTIME_NAME") else "local", "runtime": os.getenv("AGENT_RUNTIME_NAME")}


ACTIONS: Dict[str, Callable[[Dict[str, Any]], Any]] = {
    "chat": _chat,
    "analysis": _analysis,
    "knowledge_chat": lambda p: orchestrator.chat(
        p.get("user_id", "demo"), p["message"], p.get("lang", "en"), p.get("holdings_persona"), bool(p.get("live"))
    ),
    "approve": lambda p: orchestrator.approve(p["action_id"], p.get("risk"), p.get("lang", "en")),
    "reject": lambda p: orchestrator.reject(p["action_id"], p.get("lang", "en")),
    "accounts": _accounts,
    "delete_account": _delete_account,
    "trade_check": _trade_check,
    "sentiment_ask": _sentiment_ask,
    "runtime": _runtime,
    "set_investor": lambda p: investor_store.save(
        p.get("user_id", "demo"), p["persona_id"], p.get("account_type"), p.get("profile"),
        known_profile_at=p["known_profile_at"] if "known_profile_at" in p else investor_store.UNSET,
    ),
    "clear_profile": lambda p: investor_store.clear_profile(p.get("user_id", "demo")),
    "get_investor": lambda p: investor_store.load(p.get("user_id", "demo")),
}


def handle(action: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    """Run one action. Raises AgentError for anything the caller should be told about."""
    run = ACTIONS.get(action)
    if run is None:
        raise AgentError(400, f"unknown agent action: {action}")
    try:
        return run(payload or {})
    except AgentError:
        raise
    except ServiceConfigurationError as exc:
        raise AgentError(503, str(exc)) from exc
    except ExternalServiceError as exc:
        raise AgentError(502, str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise AgentError(422, str(exc)) from exc
    except KeyError as exc:
        raise AgentError(422, f"missing or unknown field: {exc}") from exc
