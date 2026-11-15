"""The agents behind AgentCore: the runtime's HTTP entry point and the backend's gateway to it."""
import importlib.util
import io
import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from app.agent_app import AgentError
from app.services import agent_runtime
from app.services.errors import ExternalServiceError, ServiceConfigurationError

ROOT = Path(__file__).resolve().parents[2]


def load_main():
    sys.path.insert(0, str(ROOT / "backend"))  # the runtime zip has `app/` next to main.py
    spec = importlib.util.spec_from_file_location("agentcore_main", ROOT / "agentcore" / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def server():
    main = load_main()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), main.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def post(url, body):
    request = urllib.request.Request(url + "/invocations", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def test_ping_reports_healthy(server):
    with urllib.request.urlopen(server + "/ping") as response:
        assert json.loads(response.read())["status"] == "Healthy"


def test_the_runtime_runs_the_agents_and_returns_an_envelope(server):
    reply = post(server, json.dumps({"action": "chat", "payload": {"message": "Tell me about recession risk"}}).encode())
    assert reply["ok"] is True and "answer" in reply["result"] and reply["result"]["trace"]


def test_the_runtime_runs_the_trade_check_agents(server):
    reply = post(server, json.dumps({"action": "trade_check", "payload": {"ticker": "NVDA", "action": "sell", "persona": "amira", "live": True}}).encode())
    assert reply["ok"] and reply["result"]["verdict"] == "panic_risk" and reply["result"]["persona_fit"]["persona"]["name"] == "Amira"


def test_failures_come_back_as_envelopes_not_crashes(server):
    assert post(server, b'{"action": "nope"}') == {"ok": False, "status": 400, "detail": "unknown agent action: nope"}
    assert post(server, b"not json")["status"] == 400
    not_live = post(server, json.dumps({"action": "trade_check", "payload": {"ticker": "NVDA", "action": "sell"}}).encode())
    assert not_live["ok"] is False and not_live["status"] == 409


class FakeAgentCore:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def invoke_agent_runtime(self, **kw):
        self.calls.append(kw)
        return {"response": io.BytesIO(json.dumps(self.reply).encode())}


def deployed(monkeypatch, reply):
    monkeypatch.setenv("AGENTS", "agentcore")
    monkeypatch.delenv("ORCHESTRATOR_AGENT_ARN", raising=False)  # a developer's .env must not leak into the test
    monkeypatch.delenv("INVESTOR_AGENT_ARN", raising=False)
    monkeypatch.setenv("AGENT_RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-east-1:1:runtime/x")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    fake = FakeAgentCore(reply)
    monkeypatch.setattr("boto3.client", lambda name, **kw: fake)
    return fake


def test_gateway_forwards_to_the_aws_runtime_and_unwraps_the_result(monkeypatch):
    fake = deployed(monkeypatch, {"ok": True, "result": {"answer": "hi"}})
    assert agent_runtime.call("chat", {"message": "hi"}, "demo") == {"answer": "hi"}
    sent = fake.calls[0]
    assert sent["agentRuntimeArn"].endswith("runtime/x") and 33 <= len(sent["runtimeSessionId"]) <= 256
    assert json.loads(sent["payload"]) == {"action": "chat", "payload": {"message": "hi"}}


def test_every_call_goes_to_the_orchestrator_agent_when_it_is_configured(monkeypatch):
    fake = deployed(monkeypatch, {"ok": True, "result": {}})
    monkeypatch.setenv("ORCHESTRATOR_AGENT_ARN", "arn:aws:bedrock-agentcore:us-east-1:1:runtime/orchestrator")
    for action in ("chat", "accounts", "set_investor", "trade_check", "sentiment_ask", "analysis", "preload"):
        agent_runtime.call(action, {}, "demo")
    assert len(fake.calls) == 7 and all(c["agentRuntimeArn"].endswith("runtime/orchestrator") for c in fake.calls)


def test_gateway_never_falls_back_to_local_agents(monkeypatch):
    monkeypatch.setenv("AGENTS", "agentcore")
    monkeypatch.delenv("AGENT_RUNTIME_ARN", raising=False)
    monkeypatch.delenv("ORCHESTRATOR_AGENT_ARN", raising=False)
    with pytest.raises(ServiceConfigurationError):
        agent_runtime.call("chat", {"message": "hi"})


def test_gateway_maps_runtime_errors(monkeypatch):
    deployed(monkeypatch, {"ok": False, "status": 409, "detail": "refresh the live market"})
    with pytest.raises(AgentError) as caught:
        agent_runtime.call("trade_check", {})
    assert caught.value.status == 409

    def boom(name, **kw):
        raise RuntimeError("expired token")

    monkeypatch.setattr("boto3.client", boom)
    with pytest.raises(ExternalServiceError):
        agent_runtime.call("chat", {"message": "hi"})


def test_api_returns_the_runtime_status_codes(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    deployed(monkeypatch, {"ok": False, "status": 409, "detail": "refresh the live market"})
    response = TestClient(app).get("/api/trade-check/NVDA", params={"action": "sell"})
    assert response.status_code == 409 and response.json()["detail"] == "refresh the live market"


def test_chat_trace_starts_with_the_agentcore_runtime_when_deployed(monkeypatch):
    from app import agent_app

    monkeypatch.setenv("AGENT_RUNTIME_NAME", "portfolioguard_agents_workshop")
    reply = agent_app.handle("chat", {"message": "Tell me about recession risk"})
    assert reply["trace"][0]["agent"] == "AgentCore Runtime"
    assert "portfolioguard_agents_workshop" in reply["trace"][0]["action"]
    assert reply["trace"][1]["agent"] == "Global Orchestrator"
    monkeypatch.delenv("AGENT_RUNTIME_NAME")
    assert agent_app.handle("chat", {"message": "Tell me about recession risk"})["trace"][0]["agent"] == "Global Orchestrator"
