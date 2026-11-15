from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app import store
from app.services.errors import ExternalServiceError


def test_health_contract() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "portfolioguard-api"}


def test_local_dashboard_origins_are_allowed() -> None:
    client = TestClient(app)
    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        response = client.options(
            "/api/analysis",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_analysis_validation_rejects_invalid_weight_total() -> None:
    response = TestClient(app).post(
        "/api/analysis",
        json={
            "persona_id": "amira",
            "account_type": "TFSA",
            "strategy_allocations": {
                "growth": 0.6,
                "dividend": 0.2,
                "momentum": 0.1,
                "preservation": 0.2,
            },
            "shift": {
                "from_strategy": "growth",
                "to_strategy": "dividend",
                "amount": 0.2,
            },
            "start_date": "2023-11-13",
            "end_date": "2026-11-12",
        },
    )
    assert response.status_code == 422
    assert "strategy weights must sum to 1" in response.text


def test_analysis_fails_closed_when_aws_is_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("LAMBDA_FUNCTION_NAME", raising=False)

    response = TestClient(app).post("/api/analysis", json={})

    assert response.status_code == 503
    assert "AWS_REGION and LAMBDA_FUNCTION_NAME are required" in response.text


def test_analysis_maps_live_aws_failure_to_bad_gateway(monkeypatch) -> None:
    def fail(_request):
        raise ExternalServiceError("financial Lambda failed: unavailable")

    monkeypatch.setattr("app.agent_app.orchestrator.run", fail)

    response = TestClient(app).post("/api/analysis", json={})

    assert response.status_code == 502
    assert response.json()["detail"] == "financial Lambda failed: unavailable"


def test_meta_reports_configuration_without_calling_aws(monkeypatch) -> None:
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LAMBDA_FUNCTION_NAME", "portfolioguard-workshop-financial-tools")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
    monkeypatch.setenv("S3_BUCKET", "portfolioguard-workshop-data-example")
    monkeypatch.setenv("DATA_PREFIX", "starter/v1")

    response = TestClient(app).get("/api/meta")

    assert response.status_code == 200
    integrations = response.json()["integrations"]
    assert integrations["region"] == "us-east-1"
    assert integrations["lambda"]["configured"] is True
    assert integrations["bedrock"]["configured"] is True
    assert integrations["dataset"]["configured"] is True
    assert integrations["bedrock"]["detail"] == "us.amazon.nova-lite-v1:0"


def test_conversational_account_proposal_requires_approval() -> None:
    store.ACCOUNTS.clear()
    store.PENDING.clear()
    client = TestClient(app)

    proposal_response = client.post(
        "/api/chat",
        json={
            "user_id": "test-user",
            "message": "Open a long-term account with balanced risk",
        },
    )

    assert proposal_response.status_code == 200
    proposal = proposal_response.json()["proposal"]
    assert proposal["type"] == "create_account"
    assert client.get("/api/accounts?user_id=test-user").json() == []

    approval_response = client.post(
        f"/api/actions/{proposal['id']}/approve",
        json={"risk": "balanced"},
    )

    assert approval_response.status_code == 200
    accounts = client.get("/api/accounts?user_id=test-user").json()
    assert len(accounts) == 1
    assert accounts[0]["type"] == "RRSP"
    assert accounts[0]["risk"] == "balanced"
    store.ACCOUNTS.clear()
    store.PENDING.clear()
