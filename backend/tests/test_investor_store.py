"""The selected investor kept in S3: validation, storage, and how the agents use it."""
import io
import json

import pytest

from app import agent_app
from app.agents import trade_pipeline
from app.services import investor_store
from app.services.errors import ExternalServiceError
from fastapi.testclient import TestClient
from app.main import app


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.puts = []

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.puts.append((Bucket, Key))
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            err = Exception("missing")
            err.response = {"Error": {"Code": "NoSuchKey"}}
            raise err
        return {"Body": io.BytesIO(self.objects[Key])}


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    investor_store._MEMORY.clear()
    monkeypatch.setenv("EXPLAINER", "rules")


@pytest.fixture
def s3(monkeypatch):
    fake = FakeS3()
    monkeypatch.setenv("DATA_BUCKET", "bucket")
    monkeypatch.setattr(investor_store, "_client", lambda: fake)
    return fake


def test_saving_writes_the_persona_and_its_adjusted_band_to_s3(s3):
    record = investor_store.save("demo", "amira", "RRSP")
    assert s3.puts == [("bucket", "personas/demo/current.json")]
    stored = json.loads(s3.objects["personas/demo/current.json"])
    assert (stored["persona_id"], stored["account_type"]) == ("amira", "RRSP")
    assert (stored["base_risk_band"], stored["risk_band"]) == ("high", "mid")  # the RRSP rule is already applied
    assert record["stored_in"] == "s3://bucket/personas/demo/current.json"
    assert investor_store.load("demo")["risk_band"] == "mid"


def test_an_unknown_user_has_no_saved_investor(s3):
    assert investor_store.load("someone-new") is None


@pytest.mark.parametrize("bad", ["../secrets", "a/b", "a.b", "", "x" * 65, "demo/../x"])
def test_user_ids_cannot_escape_the_personas_prefix(s3, bad):
    with pytest.raises(ValueError):
        investor_store.save(bad, "amira")
    with pytest.raises(ValueError):
        investor_store.load(bad)
    assert s3.puts == []


def test_only_known_investors_and_accounts_are_saved(s3):
    with pytest.raises(ValueError):
        investor_store.save("demo", "mallory")
    with pytest.raises(ValueError):
        investor_store.save("demo", "amira", "Offshore")


def test_a_tampered_stored_file_is_ignored(s3):
    s3.objects["personas/demo/current.json"] = json.dumps({"persona_id": "mallory", "account_type": None}).encode()
    assert investor_store.load("demo") is None
    s3.objects["personas/demo/current.json"] = b"not json"
    assert investor_store.load("demo") is None


def test_s3_failures_are_reported_not_swallowed(monkeypatch):
    class Broken:
        def put_object(self, **kw):
            raise RuntimeError("denied")

        def get_object(self, **kw):
            raise RuntimeError("denied")

    monkeypatch.setenv("DATA_BUCKET", "bucket")
    monkeypatch.setattr(investor_store, "_client", lambda: Broken())
    with pytest.raises(ExternalServiceError):
        investor_store.save("demo", "amira")
    with pytest.raises(ExternalServiceError):
        investor_store.load("demo")


def test_without_a_bucket_the_investor_lives_in_memory_for_tests_and_offline_work():
    assert investor_store.save("demo", "robert")["stored_in"] == "memory"
    assert investor_store.load("demo")["persona_id"] == "robert"


# ---- how the agents use it -------------------------------------------------------------

def check(persona=None, account=None, user="demo", ticker="NVDA"):
    return trade_pipeline.run("sell", ticker, persona, account, True, "en", user_id=user)


def test_a_check_without_an_investor_reads_the_saved_one():
    investor_store.save("demo", "robert")
    out = check()
    assert out["intake"]["persona_name"] == "Robert" and out["trade_check"]["verdict"] == "evidence_supported"
    assert "read from S3" in out["trace"][0]["action"]


def test_swapping_the_investor_changes_the_verdict_for_the_same_stock():
    verdicts = {}
    for who in ("robert", "mateo", "amira"):
        investor_store.save("demo", who)
        verdicts[who] = check()["trade_check"]["verdict"]
    assert verdicts == {"robert": "evidence_supported", "mateo": "mixed", "amira": "panic_risk"}


def test_a_request_that_names_an_investor_wins_and_updates_the_saved_one():
    investor_store.save("demo", "robert")
    out = check(persona="amira")
    assert out["intake"]["persona_name"] == "Amira" and "saved to S3" in out["trace"][0]["action"]
    assert investor_store.load("demo")["persona_id"] == "amira"


def test_the_account_choice_is_saved_and_lowers_the_band():
    out = check(persona="amira", account="RRSP")
    assert out["intake"]["risk_band"] == "mid"
    assert investor_store.load("demo")["account_type"] == "RRSP"


def test_users_do_not_see_each_others_investor():
    investor_store.save("alice", "robert")
    investor_store.save("bob", "amira")
    assert check(user="alice")["intake"]["persona_name"] == "Robert"
    assert check(user="bob")["intake"]["persona_name"] == "Amira"
    assert check(user="carol")["intake"]["persona_name"] is None  # nothing saved, nothing assumed


def test_a_store_outage_does_not_break_the_check(monkeypatch):
    def down(*a, **k):
        raise ExternalServiceError("s3 down")

    monkeypatch.setattr(investor_store, "load", down)
    out = check(persona="amira")
    assert out["trade_check"]["verdict"] == "panic_risk" and "unavailable" in out["trace"][0]["action"]


# ---- API ---------------------------------------------------------------------------------

def test_api_saves_and_reads_the_investor():
    client = TestClient(app)
    assert client.get("/api/investor", params={"user_id": "dana"}).status_code == 404
    saved = client.put("/api/investor", json={"persona_id": "mateo", "account_type": "TFSA", "user_id": "dana"}).json()
    assert saved["risk_band"] == "mid" and saved["persona_name"] == "Mateo"
    assert client.get("/api/investor", params={"user_id": "dana"}).json()["persona_id"] == "mateo"


def test_api_rejects_bad_input():
    client = TestClient(app)
    assert client.put("/api/investor", json={"persona_id": "mallory"}).status_code == 422
    assert client.put("/api/investor", json={"persona_id": "amira", "user_id": "../x"}).status_code == 422
    assert client.put("/api/investor", json={"persona_id": "amira", "account_type": "Offshore"}).status_code == 422


def test_trade_check_endpoint_uses_the_saved_investor():
    client = TestClient(app)
    client.put("/api/investor", json={"persona_id": "robert", "user_id": "erin"})
    body = client.get("/api/trade-check/NVDA", params={"action": "sell", "live": "true", "user_id": "erin"}).json()
    assert body["verdict"] == "evidence_supported" and body["intake"]["persona_name"] == "Robert"


def test_a_bad_user_id_is_a_422_before_any_aws_call(monkeypatch):
    monkeypatch.setenv("AGENTS", "agentcore")
    monkeypatch.setenv("AGENT_RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-east-1:1:runtime/x")
    monkeypatch.setattr("boto3.client", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not call AWS")))
    response = TestClient(app).get("/api/investor", params={"user_id": "../secrets"})
    assert response.status_code == 422
