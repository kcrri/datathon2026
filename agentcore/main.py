"""AgentCore Runtime entry point for the PortfolioGuard agents.

AgentCore starts this file and talks to it over HTTP on port 8080:

    GET  /ping          health check
    POST /invocations   {"action": "...", "payload": {...}} -> {"ok": true, "result": ...}
                        or {"ok": false, "status": <http status>, "detail": "..."}

The orchestrator and every agent run here, in the AWS account. They call the financial-tools
Lambda for calculations (market data in S3) and Amazon Bedrock for explanations. The standard
library server keeps the deployment package small; all logic is in ``app.agent_app``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("AGENTS", "local")  # inside the runtime the handler runs in-process

from app import agent_app  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("portfolioguard.agents")
MAX_BODY = 1_000_000


def run(body: bytes) -> tuple[int, dict]:
    """Execute one invocation; always returns an envelope, never raises."""
    started = time.monotonic()
    action = "unknown"
    try:
        request = json.loads(body or b"{}")
        action = str(request.get("action", ""))
        result = agent_app.handle(action, request.get("payload") or {})
        envelope, status = {"ok": True, "result": result}, 200
    except agent_app.AgentError as exc:
        envelope, status = {"ok": False, "status": exc.status, "detail": exc.detail}, 200
    except json.JSONDecodeError:
        envelope, status = {"ok": False, "status": 400, "detail": "request body must be JSON"}, 200
    except Exception as exc:  # last resort: report it, keep the runtime alive
        log.exception("agent action failed")
        envelope, status = {"ok": False, "status": 500, "detail": f"agent error: {type(exc).__name__}"}, 200
    log.info(json.dumps({"event": "agent_action", "action": action, "ok": envelope["ok"], "ms": round((time.monotonic() - started) * 1000)}))
    return status, envelope


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        if self.path.split("?")[0] == "/ping":
            self._send(200, {"status": "Healthy", "time_of_last_update": int(time.time())})
        else:
            self._send(404, {"detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?")[0] != "/invocations":
            return self._send(404, {"detail": "not found"})
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._send(413, {"ok": False, "status": 413, "detail": "request too large"})
        status, envelope = run(self.rfile.read(length))
        self._send(status, envelope)

    def log_message(self, *_args) -> None:  # request lines go through our own structured log
        return


def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    log.info(json.dumps({"event": "agents_starting", "port": port, "runtime": os.getenv("AGENT_RUNTIME_NAME")}))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
