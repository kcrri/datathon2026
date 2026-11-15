import pytest
from fastapi.testclient import TestClient

from app.agents.signals import sentiment
from app.main import app
from app.services import sell_guard_service
from app.services.errors import ExternalServiceError

class MarketClient(TestClient):
    """The API keeps no market state, so the client sends ``live`` with each request, as the web app does."""

    live = False

    def get(self, url, **kw):
        if self.live:
            kw["params"] = {**(kw.get("params") or {}), "live": "true"}
        return super().get(url, **kw)

    def post(self, url, **kw):
        if url == "/api/market/refresh":
            self.live = True
        elif url == "/api/market/reset":
            self.live = False
        elif self.live and kw.get("json") is not None:
            kw["json"] = {**kw["json"], "live": True}
        return super().post(url, **kw)


client = MarketClient(app)


class FakeBedrock:
    """Plays a scripted Converse conversation and records what it was asked."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def converse(self, **kwargs):
        self.requests.append(kwargs)
        return {"output": {"message": self.replies.pop(0)}}


def tool_call(ticker, name="get_ticker_sentiment"):
    return {"role": "assistant", "content": [{"toolUse": {"toolUseId": "t1", "name": name, "input": {"ticker": ticker}}}]}


def text(answer):
    return {"role": "assistant", "content": [{"text": answer}]}


def setup_function():
    client.post("/api/market/reset")


def test_summary_is_deterministic_and_has_categories_and_peers():
    client.post("/api/market/refresh")
    first = sell_guard_service.sentiment_summary("ENB.TO", live=True)
    assert first == sell_guard_service.sentiment_summary("ENB.TO", live=True)
    assert first["mean_sentiment"] < -0.3
    assert "regulatory" in first["categories"]
    assert sell_guard_service.sentiment_summary("QQQ", live=True)["peer_sentiment"] is not None


def test_unknown_ticker_is_rejected():
    with pytest.raises(ValueError):
        sell_guard_service.sentiment_summary("NOPE")
    assert client.get("/api/sentiment/NOPE").status_code == 404


def test_endpoint_returns_evidence_without_calling_a_model():
    client.post("/api/market/refresh")
    body = client.get("/api/sentiment/enb.to").json()
    assert body["ticker"] == "ENB.TO" and body["computed_by"] == "local-engine"


def test_model_asks_for_sentiment_through_the_tool(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    client.post("/api/market/refresh")
    fake = FakeBedrock([tool_call("ENB.TO"), text("The pipeline news tone is clearly negative.")])
    result = sentiment.ask("How is the news for Enbridge?", bedrock_client=fake)
    assert result["answer"].startswith("The pipeline")
    assert [c["tool"] for c in result["tool_calls"]] == ["get_ticker_sentiment"]
    assert result["tool_calls"][0]["result"]["ticker"] == "ENB.TO"
    # the tool result was sent back to the model
    assert "toolResult" in fake.requests[1]["messages"][-2]["content"][0]
    assert fake.requests[0]["toolConfig"]["tools"][0]["toolSpec"]["name"] == "get_ticker_sentiment"


def test_unknown_ticker_from_model_becomes_a_tool_error_not_a_crash(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    fake = FakeBedrock([tool_call("FAKE"), text("I could not find that ticker.")])
    result = sentiment.ask("Tell me about FAKE", bedrock_client=fake)
    assert "error" in result["tool_calls"][0]["result"]


def test_unknown_tool_is_refused():
    assert "error" in sentiment.run_tool("delete_everything", {})


def test_answer_with_digits_is_rejected(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    fake = FakeBedrock([text("Sentiment is -0.8 for this stock.")])
    with pytest.raises(ExternalServiceError):
        sentiment.ask("How is NVDA?", bedrock_client=fake)


def test_endless_tool_requests_are_stopped(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    fake = FakeBedrock([tool_call("NVDA")] * 10)
    with pytest.raises(ExternalServiceError):
        sentiment.ask("loop", bedrock_client=fake)


def test_ask_endpoint_reports_missing_configuration(monkeypatch):
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    assert client.post("/api/sentiment/ask", json={"question": "How is NVDA?"}).status_code == 503
