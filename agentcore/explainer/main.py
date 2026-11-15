"""Explainer agent (AgentCore runtime): the pop-up warning, then the full detail for the chat.

Tool: ``write_explanation``. It finds the investor's position and how the verdict fits their
persona, then asks an Amazon Bedrock model to write the pop-up title and the chat detail. The text
is checked before it is used: it may contain no digits and may cite only the Classifier's
evidence IDs. If a check fails the fixed wording is used instead.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from common import envelope, owned, run_agent  # noqa: E402

app = BedrockAgentCoreApp()

SYSTEM = """You are the Explainer agent of PortfolioGuard AI. Call write_explanation exactly once, then reply with the
single word done. The tool writes and checks the text; do not write any text yourself."""


def work(p: dict) -> dict:
    from app.agents import explainer, persona_fit
    from app.domain.presets import PERSONAS
    from app.services import sell_guard_service

    action, ticker, result, who = p["action"], str(p["ticker"]).strip().upper(), p["result"], p["intake"]
    persona_id, lang = who.get("persona_id") or p.get("persona"), p.get("lang", "en")
    captured: dict = {}

    def write_explanation() -> dict:
        """Write the pop-up warning and the chat detail from the Classifier's evidence only."""
        position = fit = explanation = None
        if persona_id in PERSONAS:
            position = sell_guard_service.investor_position(persona_id, ticker, action, p.get("account_type"), bool(p.get("live")))
            fit = persona_fit.fit(persona_id, action, ticker, result["verdict"], position, lang, risk_band=who.get("risk_band"))
        note = "fixed wording (the explainer model is switched off)"
        if explainer.enabled():
            try:
                explanation = explainer.explain(action, result, fit, who, lang)
                note = "pop-up and chat detail written with Amazon Bedrock, citing only the Classifier's evidence IDs"
                if explanation is None:
                    note = "the model's text was rejected by the checks, so the fixed wording is used"
            except Exception as exc:
                note = f"the explainer was unavailable ({type(exc).__name__}), so the fixed wording is used"
        captured["explained"] = {"explanation": explanation, "persona_fit": fit, "position": position, "note": note}
        return captured["explained"]

    return run_agent("explainer", SYSTEM, [write_explanation], f"Explain the {action} of {ticker}.", captured, "explained")


def handle_owned(action: str, payload: dict):
    return owned(action, payload)


OWNED = {'knowledge_chat', 'chat', 'analysis'}  # actions this agent runs itself, directly, without a model loop


def serve(request: dict):
    """One request: ``{"action": ..., "payload": {...}}``. No action means this agent's default step."""
    action = request.get("action")
    payload = request.get("payload") or {}
    if action in OWNED:
        return handle_owned(action, payload)
    return work(payload)


@app.entrypoint
def invoke(payload, context=None):
    return envelope(lambda: serve(payload or {}))


if __name__ == "__main__":
    app.run()
