"""HTTP endpoints for the MCP server, and the info the "Connect Claude" dialog shows.

The connector URL carries a per-user token (``/mcp/<user>.<signature>``), because Claude's custom
connectors take a URL. The token is an HMAC of the user id under ``MCP_SECRET``, so it cannot be
forged or switched to another user, and it only ever lets the holder submit or read that one
user's persona. ``Authorization: Bearer <token>`` is accepted too, for clients that send headers.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app import mcp_server
from app.services.investor_store import USER_ID

router = APIRouter()
_SECRET = os.getenv("MCP_SECRET") or secrets.token_hex(32)  # without MCP_SECRET the URL changes on restart
ALLOWED_ORIGIN_HOSTS = ("localhost", "127.0.0.1", "claude.ai", "claude.com", "anthropic.com")
RATE_LIMIT, RATE_WINDOW = 60, 60.0  # requests per token per minute
_HITS: Dict[str, Deque[float]] = defaultdict(deque)


def _secret() -> str:
    return os.getenv("MCP_SECRET") or _SECRET


def make_token(user_id: str) -> str:
    if not USER_ID.fullmatch(user_id):
        raise ValueError("invalid user id")
    return f"{user_id}.{hmac.new(_secret().encode(), f'mcp:{user_id}'.encode(), hashlib.sha256).hexdigest()[:32]}"


def verify_token(token: Optional[str]) -> Optional[str]:
    """The user id a valid token belongs to, else None."""
    if not token or "." not in token:
        return None
    user_id, _, signature = token.rpartition(".")
    if not USER_ID.fullmatch(user_id):
        return None
    expected = make_token(user_id).rpartition(".")[2]
    return user_id if hmac.compare_digest(signature, expected) else None


def _origin_allowed(origin: Optional[str]) -> bool:
    if not origin:  # command-line and server-to-server clients send none
        return True
    host = (urlparse(origin).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in ALLOWED_ORIGIN_HOSTS)


def _client_name(request: Request) -> str:
    agent = request.headers.get("user-agent", "")
    return re.sub(r"[^\w .,/()+-]", "", agent)[:60] or "unknown"


def _rate_limited(token: str) -> bool:
    now = time.monotonic()
    hits = _HITS[token]
    while hits and now - hits[0] > RATE_WINDOW:
        hits.popleft()
    if len(hits) >= RATE_LIMIT:
        return True
    hits.append(now)
    return False


async def _serve(request: Request, token: Optional[str]) -> Response:
    if not _origin_allowed(request.headers.get("origin")):
        return JSONResponse({"error": "origin not allowed"}, status_code=403)
    bearer = request.headers.get("authorization", "")
    token = token or (bearer[7:] if bearer.lower().startswith("bearer ") else None)
    user_id = verify_token(token)
    if not user_id:
        return JSONResponse({"error": "missing or invalid connector token"}, status_code=401)
    if _rate_limited(token or ""):
        return JSONResponse({"error": "too many requests"}, status_code=429, headers={"Retry-After": "30"})
    try:
        message = await request.json()
    except ValueError:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}, status_code=400)
    if isinstance(message, list):  # batching was removed from the protocol
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "batch requests are not supported"}}, status_code=400)
    reply = mcp_server.handle(message, user_id, _client_name(request))
    if reply is None:  # a notification
        return Response(status_code=202)
    return JSONResponse(reply)


@router.post("/mcp/{token}")
async def mcp_with_token(token: str, request: Request) -> Response:
    return await _serve(request, token)


@router.post("/mcp")
async def mcp_with_header(request: Request) -> Response:
    return await _serve(request, None)


@router.api_route("/mcp/{token}", methods=["GET", "DELETE"])
@router.api_route("/mcp", methods=["GET", "DELETE"])
async def mcp_not_streaming(token: str = "") -> Response:
    """No sessions and no server-to-client stream: the protocol says to answer 405."""
    return Response(status_code=405, headers={"Allow": "POST"})


@router.get("/api/mcp/info")
def mcp_info(request: Request, user_id: str = "demo") -> Dict[str, Any]:
    """What the "Connect Claude" dialog shows: the connector URL and how to add it."""
    if not USER_ID.fullmatch(user_id):
        raise HTTPException(status_code=422, detail="invalid user id")
    base = (os.getenv("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")
    token = make_token(user_id)
    host = (urlparse(base).hostname or "").lower()
    return {
        "url": f"{base}/mcp/{token}",
        "base_url": base,
        "token": token,
        "local_only": host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local"),
        "stable": bool(os.getenv("MCP_SECRET")),
        "tools": [{"name": t["name"], "title": t["title"], "description": t["description"], "input_schema": t["inputSchema"]} for t in mcp_server.TOOLS],
        "example": {"risk": "low", "horizon": "retiring in 5 years", "goals": ["protect my savings", "steady income"]},
        "server": mcp_server.SERVER_INFO,
    }
