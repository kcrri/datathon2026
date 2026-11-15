import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("FEATURES_FILE", str(tmp_path / "features.json"))


def test_every_page_is_on_by_default():
    flags = client.get("/api/features").json()["flags"]
    assert set(flags) == {"analysis", "holdings", "assistant", "accounts", "insights"}
    assert all(flags.values())


def test_a_page_can_be_switched_off_and_on_and_the_choice_is_saved():
    off = client.put("/api/features/holdings", json={"enabled": False}).json()["flags"]
    assert off["holdings"] is False and off["analysis"] is True
    assert client.get("/api/features").json()["flags"]["holdings"] is False  # read back from the file
    on = client.put("/api/features/holdings", json={"enabled": True}).json()["flags"]
    assert on["holdings"] is True


def test_reset_restores_defaults():
    client.put("/api/features/assistant", json={"enabled": False})
    client.put("/api/features/accounts", json={"enabled": False})
    flags = client.post("/api/features/reset").json()["flags"]
    assert all(flags.values())


def test_unknown_page_and_bad_body_are_rejected():
    assert client.put("/api/features/nope", json={"enabled": False}).status_code == 404
    assert client.put("/api/features/holdings", json={"enabled": "maybe"}).status_code == 422


def test_corrupt_file_falls_back_to_defaults(tmp_path, monkeypatch):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    monkeypatch.setenv("FEATURES_FILE", str(broken))
    assert all(client.get("/api/features").json()["flags"].values())
