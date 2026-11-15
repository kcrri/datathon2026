#!/usr/bin/env python3
"""Does touching a button in the UI touch the agents? An end-to-end check against the real AWS agents.

For each button it makes the same request the UI makes (to your running backend), then counts the
"Invocation completed" lines each AgentCore runtime logged during that button's window and compares
them with the agents that button should reach. It exits 0 when every button reached its agents.

    backend/.venv/bin/python scripts/test_buttons_call_agents.py            # backend on :8001
    BACKEND=http://127.0.0.1:8000 backend/.venv/bin/python scripts/test_buttons_call_agents.py

Needs AWS credentials for the portfolioguard-workshop profile (AWS_PROFILE) and the backend running
with ORCHESTRATOR_AGENT_ARN set. Each run makes about four real agent calls (a few cents of Bedrock).
CloudWatch lags by a few seconds, so the run takes about a minute and a half.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

import boto3

BACKEND = os.getenv("BACKEND", "http://127.0.0.1:8001").rstrip("/")
REGION = os.getenv("AWS_REGION", "us-east-1")
RUNTIMES = {  # agent -> runtime id (stack portfolioguard-workshop-agentcore-agents)
    "orchestrator": "portfolioguard_orchestrator_workshop-vWjy1M4uOO",
    "intake": "portfolioguard_intake_workshop-jKKeBL2XwN",
    "market": "portfolioguard_market_workshop-jQoAns2q52",
    "classifier": "portfolioguard_classifier_workshop-LWXMOlCXFp",
    "explainer": "portfolioguard_explainer_workshop-oMF7F7E1SS",
}
USER = "button-test"

# (button, request, agents that must be called, seconds to let background work finish)
BUTTONS = [
    ("Refresh market", ("POST", "/api/market/refresh?user_id=" + USER, None), {"orchestrator", "market", "classifier"}, 25),
    ("Switch investor to Mateo", ("PUT", "/api/investor", {"persona_id": "mateo", "account_type": "TFSA", "user_id": USER}), {"orchestrator", "intake"}, 3),
    ("Sell NVDA (as Robert)", ("GET", "/api/trade-check/NVDA?action=sell&persona=robert&live=true&user_id=" + USER, None), {"orchestrator", "intake", "market", "classifier", "explainer"}, 3),
    ("Chat: should I sell nvidia?", ("POST", "/api/chat", {"user_id": USER, "message": "should I sell nvidia?", "holdings_persona": "robert", "live": True, "lang": "en"}), {"orchestrator", "intake", "market", "classifier", "explainer"}, 3),
]


def http(method: str, path: str, body):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BACKEND + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:200]


def completed(logs, runtime: str, start_ms: int, end_ms: int) -> int:
    """Invocations of this runtime in the window that belong to the test user: every AgentCore log line
    carries the session ID, which contains the user ID, so the UI and other sessions are not counted."""
    count, token = 0, None
    while True:
        kwargs = dict(logGroupName=f"/aws/bedrock-agentcore/runtimes/{runtime}-DEFAULT", startTime=start_ms, endTime=end_ms, filterPattern=f'"Invocation completed" "{USER}"')
        if token:
            kwargs["nextToken"] = token
        page = logs.filter_log_events(**kwargs)
        count += len(page["events"])
        token = page.get("nextToken")
        if not token:
            return count


def main() -> int:
    status, _ = http("GET", "/api/runtime", None)
    if status != 200:
        print(f"backend not reachable at {BACKEND} (GET /api/runtime -> {status}); start it first")
        return 2
    windows = []
    for name, (method, path, body), expected, settle in BUTTONS:
        start = int(time.time() * 1000)
        code, reply = http(method, path, body)
        time.sleep(settle)
        windows.append((name, expected, start, int(time.time() * 1000), code))
        print(f"touched: {name:<32} -> HTTP {code}")
        if code != 200:
            print(f"   response: {reply}")
    print("waiting for CloudWatch to catch up ...")
    time.sleep(35)

    logs = boto3.Session(profile_name=os.getenv("AWS_PROFILE", "portfolioguard-workshop"), region_name=REGION).client("logs")
    failures = 0
    print(f"\n{'button':<32} " + " ".join(f"{a[:5]:>6}" for a in RUNTIMES) + "   result")
    for name, expected, start, end, code in windows:
        counts = {agent: completed(logs, runtime, start, end + 5_000) for agent, runtime in RUNTIMES.items()}
        missing = sorted(a for a in expected if counts[a] == 0)
        ok = code == 200 and not missing
        failures += 0 if ok else 1
        print(f"{name:<32} " + " ".join(f"{counts[a]:>6}" for a in RUNTIMES) + ("   PASS" if ok else f"   FAIL (not called: {', '.join(missing) or 'request failed'})"))
    print("\nall buttons reached their agents" if not failures else f"\n{failures} button(s) did not reach their agents")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
