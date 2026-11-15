"""Shared plumbing for the five PortfolioGuard AgentCore agents.

Each agent is its own Amazon Bedrock AgentCore runtime built with the Strands Agents SDK: a
Bedrock model that decides when to call its tool. The tools do the real work with the same
deterministic code the backend uses (``backend/app``), so no number is ever produced by a model.
An agent returns what its tool returned, not what the model wrote, and if the model skips its
tool the agent still calls it, so an invocation always has a complete, checkable result.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
for path in (HERE, os.path.join(HERE, "..", "backend")):  # in a deployed package ``app/`` sits next to main.py
    if path not in sys.path:
        sys.path.insert(0, path)


class AgentFailure(Exception):
    """A failure the caller should see, with the HTTP-style status the gateway maps."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def model():
    """The Bedrock model every agent reasons with (temperature 0 keeps tool use stable)."""
    from strands.models import BedrockModel

    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise AgentFailure(500, "BEDROCK_MODEL_ID is required")
    return BedrockModel(model_id=model_id, region_name=os.getenv("AWS_REGION"), temperature=0.0)


def run_agent(name: str, system: str, tool_fns: List[Callable[[], Dict[str, Any]]], prompt: str, captured: Dict[str, Any], key: str) -> Dict[str, Any]:
    """Let the model call its tool; return the tool's result, calling it ourselves if the model did not."""
    from strands import Agent, tool

    agent = Agent(
        name=name,
        model=model(),
        system_prompt=system,
        tools=[tool(fn) for fn in tool_fns],
        callback_handler=None,
    )
    try:
        agent(prompt)
    except Exception:  # the model path failed: the deterministic tool still answers
        pass
    if key not in captured:
        tool_fns[0]()
    return captured[key]


def owned(action: str, payload: Dict[str, Any]) -> Any:
    """Run an action this agent owns with the application's own handler (deterministic, no model loop)."""
    from app import agent_app

    return agent_app.handle(action, payload)


def envelope(fn: Callable[[], Any]) -> Dict[str, Any]:
    """Wrap an agent's work as ``{"ok": true, "result": ...}`` or ``{"ok": false, "status", "detail"}``."""
    try:
        return {"ok": True, "result": fn()}
    except AgentFailure as exc:
        return {"ok": False, "status": exc.status, "detail": exc.detail}
    except Exception as exc:
        if isinstance(getattr(exc, "status", None), int) and hasattr(exc, "detail"):  # the application's AgentError
            return {"ok": False, "status": exc.status, "detail": str(exc.detail)}
        return _failure(exc)


def _failure(exc: Exception) -> Dict[str, Any]:
    try:
        raise exc
    except AgentFailure as err:
        return {"ok": False, "status": err.status, "detail": err.detail}
    except LookupError as err:
        return {"ok": False, "status": 409, "detail": str(err)}
    except ValueError as err:
        return {"ok": False, "status": 422, "detail": str(err)}
    except Exception as err:  # report, keep the runtime alive
        return {"ok": False, "status": 500, "detail": f"agent error: {type(err).__name__}"}


def invoke_runtime(arn: str, payload: Dict[str, Any], session: str) -> Any:
    """Call another AgentCore runtime (how the Orchestrator reaches the four specialists)."""
    import boto3

    region = os.getenv("AWS_REGION")
    if not arn or not region:
        raise AgentFailure(500, "AWS_REGION and the agent runtime ARN are required")
    response = boto3.client("bedrock-agentcore", region_name=region).invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=f"portfolioguard-{session}".ljust(33, "0")[:256],
        contentType="application/json",
        accept="application/json",
        payload=json.dumps(payload).encode("utf-8"),
    )
    reply = json.loads(response["response"].read())
    if not reply.get("ok"):
        raise AgentFailure(int(reply.get("status", 502)), str(reply.get("detail", "agent runtime error")))
    return reply["result"]
