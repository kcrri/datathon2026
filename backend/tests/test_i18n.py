import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import i18n
from app.agents import knowledge
from app.main import app

client = TestClient(app)
KNOWLEDGE = Path(__file__).resolve().parents[1] / "app" / "knowledge"


def chat(message, lang):
    return client.post("/api/chat", json={"message": message, "lang": lang, "user_id": "i18n-test"}).json()


def test_french_knowledge_base_covers_every_english_entry():
    en = json.loads((KNOWLEDGE / "faq.json").read_text())
    fr = json.loads((KNOWLEDGE / "faq.fr.json").read_text())
    assert [e["id"] for e in en] == [e["id"] for e in fr]
    for english, french in zip(en, fr):
        assert french["agents"] == english["agents"]
        assert french["answer"].strip() and french["question"].strip() and french["keywords"]
        assert french["answer"] != english["answer"]


def test_every_french_question_finds_its_own_entry():
    for entry in json.loads((KNOWLEDGE / "faq.fr.json").read_text()):
        assert knowledge.match(entry["question"], "fr")["id"] == entry["id"], entry["id"]


def test_matching_ignores_accents_and_answers_in_the_chosen_language():
    assert knowledge.match("je m'inquiete d'une recession", "fr")["id"] == "recession"
    english_question_in_french_ui = knowledge.match("Should I hold crypto?", "fr")
    assert english_question_in_french_ui["id"] == "crypto"
    assert "éther" in english_question_in_french_ui["answer"]
    assert knowledge.match("devrais-je détenir des cryptomonnaies", "en")["answer"].startswith("Bitcoin")


def test_short_keywords_do_not_match_inside_other_words():
    assert knowledge.match("this method is fine", "en") is None  # "eth" is not "ethereum"
    assert knowledge.match("pour quoi faire", "fr") is None  # "or" is not "pour"


def test_english_replies_are_unchanged_by_default():
    reply = chat("I'm worried about a recession", "en")
    assert reply["answer"].startswith("Recessions are hard to time")
    assert reply["warnings"][-1] == "Simulation only. Not financial advice."


def test_french_reply_is_french_end_to_end():
    reply = chat("Je m'inquiète d'une récession", "fr")
    assert reply["answer"].startswith("Les récessions sont difficiles")
    assert reply["warnings"][-1] == "Simulation seulement. Ce ne sont pas des conseils financiers."
    assert "détecter l'intention" in reply["trace"][0]["action"]
    assert "agent de signaux macro" in reply["trace"][0]["action"]  # agent names are translated too
    assert reply["sources"][0].startswith("Base de connaissances")


def test_unknown_question_suggests_french_questions():
    reply = chat("zzz qqq", "fr")
    assert "base de connaissances" in reply["answer"]
    assert reply["suggestions"][0] == "Je m'inquiète d'une récession"


def test_account_flow_in_french_keeps_stable_keys_and_french_labels():
    reply = chat("Je veux créer un nouveau compte à long terme", "fr")
    proposal = reply["proposal"]
    assert proposal["account_type"] == "RRSP" and proposal["account_type_label"] == "REER"
    assert proposal["risk"] == "growth" and proposal["risk_label"] == "Croissance"
    assert "Je recommande un compte **REER**" in reply["answer"]
    approved = client.post(
        f"/api/actions/{proposal['id']}/approve", json={"risk": None, "lang": "fr"}
    ).json()
    assert "a été créé" in approved["answer"] and "REER #" in approved["answer"]
    declined = client.post(f"/api/actions/none/reject?lang=fr").json()
    assert declined["answer"] == "Aucun problème, rien n'a été créé."


def test_horizon_question_in_french():
    reply = chat("Je veux ouvrir un compte", "fr")
    assert reply["answer"] == "Quel est l'horizon de placement de ce compte ?"
    assert reply["suggestions"][0] == "Créer un compte à court terme"


def test_label_helpers():
    assert i18n.normalize("fr-CA") == "fr" and i18n.normalize("en-US") == "en" and i18n.normalize(None) == "en"
    assert i18n.account_name("fr", "TFSA #2") == "CELI #2"
    assert i18n.account_name("en", "TFSA #2") == "TFSA #2"
    assert i18n.strategies("fr", ["ESG", "Dividend"]) == ["ESG", "Dividendes"]
