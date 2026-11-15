"""Orchestrator agent (AgentCore runtime): the single entry point; it routes every request to the right agent.

* ``trade_check``  Intake, Market, Classifier, Explainer, in order, passing the evidence along
* ``chat``         a model reads the message: a trade question runs the pipeline; an account request
                   goes to Intake; anything else (FAQ, macro, scenarios) goes to the Explainer
* investor and account actions (``set_investor``, ``accounts``, ``approve`` ...) go to Intake
* ``sentiment_ask`` goes to the Classifier, ``analysis`` to the Explainer
* ``preload``      asks Market then Classifier to compute their answers ahead of time

It does no calculation. Its model decides when
to call each tool, but the order is enforced here: a step whose inputs are missing runs the earlier
steps first, and any step the model skipped still runs, so every invocation is complete.

Runtime ARNs come from the environment: INTAKE_AGENT_ARN, MARKET_AGENT_ARN, CLASSIFIER_AGENT_ARN
and EXPLAINER_AGENT_ARN.
"""

from __future__ import annotations

import os
import sys
import re
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from common import AgentFailure, envelope, invoke_runtime  # noqa: E402

app = BedrockAgentCoreApp()

SYSTEM = """You are the Orchestrator of PortfolioGuard AI. For a buy or sell check, call these tools in this order,
each exactly once: intake_agent, market_agent, classifier_agent, explainer_agent. Never skip one and never call
them in another order. Do not write, change or summarise any result; reply with the single word done."""

ARN_ENV = {
    "Intake": "INTAKE_AGENT_ARN",
    "Market": "MARKET_AGENT_ARN",
    "Classifier": "CLASSIFIER_AGENT_ARN",
    "Explainer": "EXPLAINER_AGENT_ARN",
}


def _call(agent: str, payload: Dict[str, Any], session: str, invoker: Callable[..., Any]) -> Any:
    return invoker(os.getenv(ARN_ENV[agent], ""), {"payload": payload}, session)


class Run:
    """One trade check: the shared state the four tools read and write."""

    def __init__(self, p: Dict[str, Any], invoker: Callable[..., Any] = invoke_runtime):
        self.p = p
        self.invoker = invoker
        self.session = str(p.get("user_id") or "demo")
        self.done: Dict[str, Any] = {}
        self.trace: list = []
        self._market_future: Optional[Future] = None
        self._pool = ThreadPoolExecutor(max_workers=1)

    def start_market(self) -> None:
        """Market does not depend on who is asking, so it starts at once, in parallel with Intake."""
        if self._market_future is None and "Market" not in self.done:
            self._market_future = self._pool.submit(
                _call, "Market", {"ticker": self.p["ticker"], "live": bool(self.p.get("live"))}, self.session, self.invoker
            )

    def _step(self, agent: str, payload: Dict[str, Any], note: Callable[[Any], str]) -> Any:
        result = _call(agent, payload, self.session, self.invoker)
        self.done[agent] = result
        self.trace.append({"agent": agent, "action": note(result), "runtime": os.getenv(ARN_ENV[agent], "").rsplit("/", 1)[-1] or agent.lower()})
        return result

    def intake(self) -> Dict[str, Any]:
        if "Intake" in self.done:
            return self.done["Intake"]
        p = self.p
        return self._step(
            "Intake",
            {k: p.get(k) for k in ("persona", "account_type", "user_id", "message", "lang")},
            lambda who: (f"read {who.get('persona_name') or 'the described investor'} as a {who['risk_band']}-risk persona" if who.get("risk_band") else "no investor selected, so the check is not personalised")
            + (f"; {who['account_rule']}" if who.get("account_rule") else "")
            + (f"; {who['note']}" if who.get("note") else ""),
        )

    def market(self) -> Dict[str, Any]:
        if "Market" in self.done:
            return self.done["Market"]
        self.start_market()
        result = self._market_future.result()
        preloaded = bool(result.pop("_preloaded", False))
        self.done["Market"] = result
        self.trace.append({
            "agent": "Market",
            "action": ("preloaded answer: " if preloaded else "")
            + f"compare the market before and after the refresh: {result['tickers_falling_together']} of {result['tracked_tickers']} tracked tickers fell together",
            "runtime": os.getenv(ARN_ENV["Market"], "").rsplit("/", 1)[-1] or "market",
        })
        return result

    def classify(self) -> Dict[str, Any]:
        if "Classifier" in self.done:
            return self.done["Classifier"]
        who, market = self.intake(), self.market()
        result = _call(
            "Classifier",
            {"action": self.p["action"], "ticker": self.p["ticker"], "market": market, "risk_band": who.get("risk_band"),
             "persona": self.p.get("persona"), "account_type": self.p.get("account_type")},
            self.session, self.invoker,
        )
        preloaded = bool(result.pop("_preloaded", False))
        self.done["Classifier"] = result
        c = result["trade_check"]
        self.trace.append({
            "agent": "Classifier",
            "action": ("preloaded answer: " if preloaded else "")
            + f"label the move {c['driver']}-driven and score it, citing {len(c['evidence'])} evidence items",
            "runtime": os.getenv(ARN_ENV["Classifier"], "").rsplit("/", 1)[-1] or "classifier",
        })
        return result

    def explain(self) -> Dict[str, Any]:
        if "Explainer" in self.done:
            return self.done["Explainer"]
        who, classified = self.intake(), self.classify()
        p = self.p
        return self._step(
            "Explainer",
            {"action": p["action"], "ticker": p["ticker"], "result": classified["trade_check"], "intake": who,
             "persona": p.get("persona"), "account_type": p.get("account_type"), "live": bool(p.get("live")), "lang": p.get("lang", "en")},
            lambda e: e.get("note", "wrote the pop-up warning and the chat detail"),
        )

    def outcome(self) -> Dict[str, Any]:
        """The finished check in the shape the chat reply needs."""
        self.finish()
        explained, classified = self.done["Explainer"], self.done["Classifier"]
        return {
            "trade_check": classified["trade_check"], "position": explained.get("position"),
            "headlines": classified.get("headlines", []), "persona_fit": explained.get("persona_fit"),
            "explanation": explained["explanation"], "intake": self.done["Intake"], "trace": self.trace,
        }

    def finish(self) -> Dict[str, Any]:
        """Run any step the model skipped, in order, and assemble the result the app expects."""
        explained = self.explain()
        classified = self.done["Classifier"]
        result = {**classified["trade_check"], "explanation": explained["explanation"]}
        if explained.get("persona_fit"):
            result["persona_fit"] = explained["persona_fit"]
        return {**result, "trace": self.trace, "intake": self.done["Intake"]}


def work(p: Dict[str, Any], invoker: Callable[..., Any] = invoke_runtime, use_model: bool = True) -> Dict[str, Any]:
    for field in ("action", "ticker"):
        if not p.get(field):
            raise AgentFailure(422, f"{field} is required")
    run = Run(p, invoker)
    run.start_market()  # independent of Intake: runs in parallel with it
    if use_model:
        from strands import Agent, tool

        from common import model

        def intake_agent() -> dict:
            """Intake agent: who is asking, as a low, mid or high risk persona."""
            return run.intake()

        def market_agent() -> dict:
            """Market agent: what changed between the two market snapshots."""
            return run.market()

        def classifier_agent() -> dict:
            """Classifier agent: market-driven or company-driven, with scores and a sentiment label."""
            return run.classify()

        def explainer_agent() -> dict:
            """Explainer agent: the pop-up warning and the full chat detail."""
            return run.explain()

        try:
            Agent(
                name="orchestrator", model=model(), system_prompt=SYSTEM,
                tools=[tool(fn) for fn in (intake_agent, market_agent, classifier_agent, explainer_agent)],
                callback_handler=None,
            )(f"Check this {p['action']} of {p['ticker']}.")
        except AgentFailure:
            raise
        except Exception:  # the model path failed: the fixed order below still completes the check
            pass
    return run.finish()


OWNERS = {  # action -> the agent that owns it
    "set_investor": "Intake", "get_investor": "Intake", "clear_profile": "Intake", "accounts": "Intake", "delete_account": "Intake",
    "approve": "Intake", "reject": "Intake",
    "sentiment_ask": "Classifier",
    "analysis": "Explainer",
}


def delegate(agent: str, action: str, payload: Dict[str, Any], invoker: Callable[..., Any] = invoke_runtime) -> Any:
    """Send one request to the agent that owns it and return its answer (a chat reply gets a routing step first)."""
    session = str(payload.get("user_id") or "demo")
    result = invoker(os.getenv(ARN_ENV[agent], ""), {"action": action, "payload": payload}, session)
    if isinstance(result, dict) and isinstance(result.get("trace"), list):
        result["trace"].insert(0, {"agent": "Global Orchestrator", "action": f"route {action} to the {agent} agent", "runtime": "orchestrator"})
    return result


def chat(p: Dict[str, Any], invoker: Callable[..., Any] = invoke_runtime) -> Dict[str, Any]:
    """Route a chat message to the right agent."""
    from app.agents import llm_router, trade_intent, trade_pipeline
    from app.agents.explainer import PREDICTION
    from app.agents.orchestrator import GlobalOrchestrator
    from app.agents.orchestrator_text import DISCLAIMER
    from app.i18n import normalize, pick
    from app.services.errors import ExternalServiceError, ServiceConfigurationError

    message, lang = p["message"], normalize(p.get("lang", "en"))
    persona, live = p.get("holdings_persona"), bool(p.get("live"))
    t = lambda en, fr: pick(lang, en, fr)  # noqa: E731
    if p.get("persona_id"):  # a scenario analysis question for a persona
        return delegate("Explainer", "chat", p, invoker)
    if GlobalOrchestrator._is_create_intent(message):  # opening an account
        return delegate("Intake", "chat", p, invoker)
    route = None
    if llm_router.enabled():
        try:
            route = llm_router._route(message, lang, persona, live, None)
        except (ExternalServiceError, ServiceConfigurationError):
            route = None  # a routing failure falls back to the knowledge agent
    if route is None or route["name"] == "other_question":
        return delegate("Explainer", "knowledge_chat", p, invoker)
    warnings = [t(DISCLAIMER, "Simulation seulement. Ce ne sont pas des conseils financiers.")]
    if route["name"] == "say":
        text = str(route["args"].get("text", "")).strip()
        if not text or re.search(r"\d", text) or PREDICTION.search(text) or len(text) > 300:
            return delegate("Explainer", "knowledge_chat", p, invoker)
        trace = [{"agent": "Global Orchestrator", "action": t("route the message with a language model: answer directly", "acheminer le message avec un modèle de langage : répondre directement"), "runtime": "orchestrator"}]
        from app.agents import knowledge

        return GlobalOrchestrator._reply(text, trace, warnings=warnings, suggestions=knowledge.suggestions(lang))
    action, raw = route["args"].get("action"), str(route["args"].get("ticker", "")).strip()
    ticker = trade_intent.resolve(raw) or (raw.upper() if re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", raw) else "")
    if action not in ("buy", "sell") or not ticker:
        return delegate("Explainer", "knowledge_chat", p, invoker)
    head = {"agent": "Global Orchestrator", "action": t(f"route the message with a language model: {action} check for {ticker}", f"acheminer le message avec un modèle de langage : vérification pour {ticker}"), "runtime": "orchestrator"}
    request = {"action": action, "ticker": ticker, "persona": persona, "account_type": p.get("account_type"), "live": live, "lang": lang, "user_id": p.get("user_id"), "message": message}
    try:
        run = Run(request, invoker)
        run.start_market()
        outcome = run.outcome()
    except AgentFailure as exc:
        if exc.status == 409:
            return GlobalOrchestrator._reply(t(f"I can check {'selling' if action == 'sell' else 'buying'} {ticker} once the live market is loaded. Refresh the market on the Holdings tab, then ask again.", "Actualisez le marché dans l'onglet Titres, puis redemandez."), [head], warnings=warnings)
        if exc.status == 422:
            return GlobalOrchestrator._reply(t(f"I don't have market data for {ticker} in this simulation.", f"Je n'ai pas de données de marché pour {ticker} dans cette simulation."), [head], warnings=warnings)
        raise
    reply = trade_pipeline.chat_reply(action, ticker, outcome, lang)
    reply["trace"] = [head] + outcome["trace"]
    return reply


def preload(p: Dict[str, Any], invoker: Callable[..., Any] = invoke_runtime) -> Dict[str, Any]:
    """Ask Market, then Classifier, to compute their answers ahead of time (neither needs to know who is asking)."""
    session = str(p.get("user_id") or "demo")
    market = invoker(os.getenv(ARN_ENV["Market"], ""), {"action": "preload", "payload": {"live": bool(p.get("live"))}}, session)
    classified = invoker(os.getenv(ARN_ENV["Classifier"], ""), {"action": "preload", "payload": {"markets": market["markets"]}}, session)
    return {"market": market["preloaded"], "classifier": classified}


def serve(request: Dict[str, Any], invoker: Callable[..., Any] = invoke_runtime, use_model: bool = True) -> Any:
    """Every call lands here and goes to the agent that owns it."""
    action = request.get("action")
    payload = request.get("payload") if "payload" in request else request
    payload = payload or {}
    if action in (None, "trade_check"):
        return work(payload, invoker, use_model)
    if action == "chat":
        return chat(payload, invoker)
    if action == "preload":
        return preload(payload, invoker)
    if action == "runtime":
        return {"agents": "agentcore", "runtime": os.getenv("AGENT_RUNTIME_NAME", "portfolioguard_orchestrator")}
    if action in OWNERS:
        return delegate(OWNERS[action], action, payload, invoker)
    raise AgentFailure(400, f"unknown agent action: {action}")


@app.entrypoint
def invoke(payload, context=None):
    request = payload or {}
    return envelope(lambda: serve(request))


if __name__ == "__main__":
    app.run()
