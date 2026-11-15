"""A remote MCP server so Claude can hand the app an investor profile.

The person adds the server's URL to Claude once (a custom connector, or ``claude mcp add``) and
asks Claude for a persona based on their profile. Claude then calls a typed tool:

    submit_persona({ "risk": "low | mid | high", "horizon": "...", "goals": ["..."] })

The app validates the arguments strictly, turns the risk into the investor the agents use (the
Intake agent's low, mid or high persona), saves it to S3 through the agent runtime and, from then
on, every trade check is personalised to it. Nothing here executes a trade or changes an account.

Transport: MCP Streamable HTTP in its simplest form. Each POST carries one JSON-RPC message and is
answered with JSON; there are no sessions and no server-to-client stream (GET answers 405).
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from app.agent_app import AgentError
from app.services import agent_runtime
from app.services.errors import ExternalServiceError, ServiceConfigurationError

PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "portfolioguard", "title": "PortfolioGuard AI", "version": "1.0.0"}
INSTRUCTIONS = (
    "PortfolioGuard AI personalises buy and sell checks to an investor. When the person asks you to set up "
    "or update their persona, read what you know about them and call submit_persona once with their risk "
    "(low, mid or high), their time horizon in plain words and their goals. Do not invent details."
)

# The risk band picks the investor template (holdings, balance); the goals and horizon are the person's own.
BAND_TO_PERSONA = {"low": "robert", "mid": "mateo", "high": "amira"}
ACCOUNT_TYPES = ("TFSA", "RRSP", "Non-registered")
MAX_GOALS, MAX_GOAL_CHARS, MAX_HORIZON_CHARS, MAX_NAME_CHARS = 6, 120, 80, 40

SUBMIT_PERSONA_SCHEMA = {
    "type": "object",
    "properties": {
        "risk": {"type": "string", "enum": ["low", "mid", "high"], "description": "How much risk the person is comfortable with: low (protect capital), mid (balanced) or high (long horizon, accepts big swings)."},
        "horizon": {"type": "string", "maxLength": MAX_HORIZON_CHARS, "description": "Their time horizon in plain words, for example \"3 to 5 years\" or \"retiring in 10 years\"."},
        "goals": {"type": "array", "minItems": 1, "maxItems": MAX_GOALS, "items": {"type": "string", "maxLength": MAX_GOAL_CHARS}, "description": "Their goals, one short phrase each, for example \"save for a house\"."},
        "name": {"type": "string", "maxLength": MAX_NAME_CHARS, "description": "Optional: what to call them."},
        "account_type": {"type": "string", "enum": list(ACCOUNT_TYPES), "description": "Optional: the account they mainly use. An RRSP lowers the risk one step."},
    },
    "required": ["risk", "horizon", "goals"],
    "additionalProperties": False,
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "submit_persona",
        "title": "Submit the person's investor persona",
        "description": "Save the person's investor persona (risk, horizon, goals) in PortfolioGuard AI so every buy or sell check is personalised to them. Simulation only; it changes no real account.",
        "inputSchema": SUBMIT_PERSONA_SCHEMA,
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "get_persona",
        "title": "Read the saved investor persona",
        "description": "Return the investor persona currently saved in PortfolioGuard AI, if any.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
]


class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class ToolInputError(ValueError):
    """The arguments were wrong; the model is told so it can correct itself."""


_ALLOWED = re.compile(r"[^\w\s.,'’()/&%+\-–:;!?]", re.UNICODE)


def clean_text(value: Any, field: str, limit: int, required: bool = True) -> Optional[str]:
    """Plain text only: no control characters, markup or line breaks, bounded length."""
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ToolInputError(f"{field} must be a string")
    text = re.sub(r"\s+", " ", _ALLOWED.sub("", value)).strip()
    if not text:
        if required:
            raise ToolInputError(f"{field} must not be empty")
        return None
    if len(text) > limit:
        raise ToolInputError(f"{field} must be at most {limit} characters")
    return text


def validate_persona(args: Any) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise ToolInputError("arguments must be an object")
    unknown = set(args) - set(SUBMIT_PERSONA_SCHEMA["properties"])
    if unknown:
        raise ToolInputError(f"unknown argument: {sorted(unknown)[0]}")
    risk = args.get("risk")
    if risk not in BAND_TO_PERSONA:
        raise ToolInputError('risk must be one of "low", "mid" or "high"')
    goals = args.get("goals")
    if not isinstance(goals, list) or not 1 <= len(goals) <= MAX_GOALS:
        raise ToolInputError(f"goals must be a list of 1 to {MAX_GOALS} short phrases")
    cleaned_goals = [clean_text(g, "each goal", MAX_GOAL_CHARS) for g in goals]
    account = args.get("account_type")
    if account is not None and account not in ACCOUNT_TYPES:
        raise ToolInputError(f"account_type must be one of {', '.join(ACCOUNT_TYPES)}")
    return {
        "risk": risk,
        "horizon": clean_text(args.get("horizon"), "horizon", MAX_HORIZON_CHARS),
        "goals": cleaned_goals,
        "name": clean_text(args.get("name"), "name", MAX_NAME_CHARS, required=False),
        "account_type": account,
    }


def _summary(record: Dict[str, Any]) -> Dict[str, Any]:
    profile = record.get("profile") or {}
    return {
        "risk": profile.get("risk") or record.get("risk_band"),
        "risk_band_used": record.get("risk_band"),
        "horizon": profile.get("horizon"),
        "goals": profile.get("goals"),
        "name": profile.get("name"),
        "account_type": record.get("account_type"),
        "saved_at": record.get("updated_at"),
    }


def _result(text: str, structured: Optional[Dict[str, Any]] = None, error: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {"content": [{"type": "text", "text": text}], "isError": error}
    if structured is not None:
        out["structuredContent"] = structured
    return out


def _submit_persona(args: Dict[str, Any], user_id: str, client: Optional[str]) -> Dict[str, Any]:
    data = validate_persona(args)
    from datetime import datetime, timezone

    profile = {
        "source": "mcp",
        "client": client or "unknown",
        "risk": data["risk"],
        "horizon": data["horizon"],
        "goals": data["goals"],
        "name": data["name"],
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    profile = {k: v for k, v in profile.items() if v is not None}
    record = agent_runtime.call(
        "set_investor",
        {"user_id": user_id, "persona_id": BAND_TO_PERSONA[data["risk"]], "account_type": data["account_type"], "profile": profile},
        user_id,
    )
    summary = _summary(record)
    note = (
        f"Saved. PortfolioGuard AI will now treat this person as a {data['risk']}-risk investor "
        f"(horizon: {data['horizon']}; goals: {'; '.join(data['goals'])}). Their buy and sell checks are personalised to it."
    )
    return _result(note, summary)


def _get_persona(_: Dict[str, Any], user_id: str, __: Optional[str]) -> Dict[str, Any]:
    record = agent_runtime.call("get_investor", {"user_id": user_id}, user_id)
    if not record:
        return _result("No persona has been saved yet. Ask the person about their risk, horizon and goals, then call submit_persona.", {"saved": False})
    return _result("The saved persona.", {"saved": True, **_summary(record)})


HANDLERS: Dict[str, Callable[[Dict[str, Any], str, Optional[str]], Dict[str, Any]]] = {
    "submit_persona": _submit_persona,
    "get_persona": _get_persona,
}


def call_tool(name: str, args: Any, user_id: str, client: Optional[str]) -> Dict[str, Any]:
    handler = HANDLERS.get(name)
    if handler is None:
        raise RpcError(-32602, f"unknown tool: {name}")
    try:
        return handler(args if args is not None else {}, user_id, client)
    except ToolInputError as exc:  # tell the model what to fix
        return _result(f"Invalid arguments: {exc}", error=True)
    except ServiceConfigurationError:
        return _result("PortfolioGuard AI is not connected to its agents right now. Try again later.", error=True)
    except AgentError as exc:  # the agents refused or failed: tell Claude, never a bare 500
        return _result(f"PortfolioGuard AI could not save the persona: {exc.detail}", error=True)
    except (ExternalServiceError, ValueError) as exc:
        return _result(f"PortfolioGuard AI could not save the persona: {exc}", error=True)


def handle(message: Any, user_id: str, client: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """One JSON-RPC message in, the response out (None for a notification, which gets no answer)."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or "method" not in message:
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request"}}
    request_id, method, params = message.get("id"), message["method"], message.get("params") or {}
    if "id" not in message:  # a notification such as notifications/initialized
        return None
    try:
        if method == "initialize":
            wanted = params.get("protocolVersion")
            result = {
                "protocolVersion": wanted if wanted in PROTOCOLS else PROTOCOLS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": INSTRUCTIONS,
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            if not isinstance(params.get("name"), str):
                raise RpcError(-32602, "tools/call needs a tool name")
            result = call_tool(params["name"], params.get("arguments"), user_id, client)
        else:
            raise RpcError(-32601, f"method not found: {method}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except RpcError as exc:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": exc.code, "message": exc.message}}
