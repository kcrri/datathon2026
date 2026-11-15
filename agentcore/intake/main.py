"""Intake agent (AgentCore runtime): who is asking, as a low, mid or high risk persona.

Tool: ``assess_investor``. It reads the saved investor from S3 when the request names none, saves
a new choice to S3, reads the persona preset (or, for a self-description, asks a Bedrock model),
and applies the account rules (an RRSP lowers the risk one step).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from common import envelope, owned, run_agent  # noqa: E402

app = BedrockAgentCoreApp()

SYSTEM = """You are the Intake agent of PortfolioGuard AI. Call assess_investor exactly once, then reply with the
single word done. Never describe or change the result; the tool is the source of truth."""


def assess(p: dict) -> dict:
    from app.agents import intake
    from app.domain.presets import PERSONAS
    from app.services import investor_store
    from app.services.errors import ExternalServiceError

    persona_id, account_type, user_id = p.get("persona"), p.get("account_type"), p.get("user_id")
    note = ""
    if user_id:
        try:
            stored = investor_store.load(user_id)
            if persona_id is None and stored:
                persona_id, account_type = stored["persona_id"], account_type or stored["account_type"]
                note = "investor read from S3"
            elif persona_id in PERSONAS and (not stored or stored["persona_id"] != persona_id or (account_type and stored["account_type"] != account_type)):
                investor_store.save(user_id, persona_id, account_type or (stored["account_type"] if stored and stored["persona_id"] == persona_id else None))
                note = "investor saved to S3"
        except (ExternalServiceError, ValueError):
            note = "S3 investor store unavailable"
    who = intake.run(persona_id, account_type, p.get("message"), p.get("lang", "en"))
    return {**who, "persona_id": who["persona_id"] or persona_id, "note": note}


def work(p: dict) -> dict:
    captured: dict = {}

    def assess_investor() -> dict:
        """Read the investor (saved in S3 or named in the request) and apply the account rules."""
        captured["intake"] = assess(p)
        return captured["intake"]

    return run_agent("intake", SYSTEM, [assess_investor], "Assess the investor.", captured, "intake")


def handle_owned(action: str, payload: dict):
    return owned(action, payload)


OWNED = {'chat', 'reject', 'approve', 'set_investor', 'clear_profile', 'accounts', 'delete_account', 'get_investor'}  # actions this agent runs itself, directly, without a model loop


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
