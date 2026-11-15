"""Send an action to the agents, which run in the AWS account (Amazon Bedrock AgentCore Runtime).

The backend is only a gateway: it signs the request with the caller's AWS credentials and the
runtime runs the orchestrator and every agent. If the runtime is not configured or cannot be
reached this fails with a clear error; it never falls back to running agents locally.
``AGENTS=local`` runs the same handler in-process and exists only for tests and offline work.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from app import agent_app
import re

from app.agent_app import AgentError
from app.services.errors import ExternalServiceError, ServiceConfigurationError


USER_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
INVESTOR_ACTIONS = frozenset({"set_investor", "get_investor", "clear_profile"})


def mode() -> str:
    value = os.getenv("AGENTS", "agentcore").strip().lower()
    if value not in ("agentcore", "local"):
        raise ServiceConfigurationError("AGENTS must be 'agentcore' or 'local'")
    return value


def _session_id(user_id: str) -> str:
    # AgentCore needs 33+ characters; one session per user keeps that user's in-memory state together.
    # A session keeps running the code it started on, so after updating the runtime change
    # AGENT_SESSION_SUFFIX (or wait for the idle timeout) to move users onto the new version.
    suffix = os.getenv("AGENT_SESSION_SUFFIX", "")
    return f"portfolioguard-agents-session-{user_id}{suffix}".ljust(33, "0")[:256]


def call(action: str, payload: Dict[str, Any], user_id: str = "demo") -> Any:
    if not USER_ID.fullmatch(user_id or ""):  # also keeps odd characters out of the session id
        raise AgentError(422, "user_id may only contain letters, digits, underscore and dash (1 to 64 characters)")
    if mode() == "local":
        return agent_app.handle(action, payload)

    # Every call goes to the Orchestrator agent (its own AgentCore runtime), which routes it to the agent that
    # owns it: Intake, Market, Classifier or Explainer. Without it, the original single runtime is used.
    # The S3-backed investor actions can be pinned to one runtime (INVESTOR_AGENT_ARN): they keep no
    # in-memory state, so any runtime that runs them gives the same answer. Unset, they follow the rule above.
    arn = (
        (os.getenv("INVESTOR_AGENT_ARN") if action in INVESTOR_ACTIONS else None)
        or os.getenv("ORCHESTRATOR_AGENT_ARN")
        or os.getenv("AGENT_RUNTIME_ARN")
    )
    region = os.getenv("AWS_REGION")
    if not arn or not region:
        raise ServiceConfigurationError("AWS_REGION and AGENT_RUNTIME_ARN are required to reach the agents")
    import boto3

    try:
        response = boto3.client("bedrock-agentcore", region_name=region).invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeSessionId=_session_id(user_id),
            contentType="application/json",
            accept="application/json",
            payload=json.dumps({"action": action, "payload": payload}).encode("utf-8"),
        )
        raw = response["response"].read()
    except Exception as exc:  # botocore errors: credentials, throttling, runtime failures
        raise ExternalServiceError(f"agent runtime call failed: {type(exc).__name__}") from exc
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExternalServiceError("agent runtime returned invalid JSON") from exc
    if not envelope.get("ok"):
        raise AgentError(int(envelope.get("status", 502)), str(envelope.get("detail", "agent runtime error")))
    return envelope["result"]
