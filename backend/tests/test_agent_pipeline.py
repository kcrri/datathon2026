"""Intake, Market, Classifier, Explainer and the Orchestrator's routing, with scripted models."""
import json

import pytest

from app import agent_app
from app.agents import explainer, intake, llm_router, trade_pipeline
from app.services import bedrock
from app.services.errors import ExternalServiceError


class Model:
    """Scripted Converse replies; records every request."""

    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def converse(self, **kw):
        self.requests.append(kw)
        if not self.replies:
            raise RuntimeError("no more scripted replies")
        return {"output": {"message": self.replies.pop(0)}}


def text(doc):
    return {"role": "assistant", "content": [{"text": doc if isinstance(doc, str) else json.dumps(doc)}]}


def route(name, **args):
    return {"role": "assistant", "content": [{"toolUse": {"toolUseId": "r1", "name": name, "input": args}}]}


GOOD = {"popup_title": "Fear can make drops feel urgent", "popup_text": "Prices fell, but so did much of the market. This may be fear talking.", "detail": "Much of the market fell together and the news is about the whole market. That can trigger fear-driven selling.", "evidence_ids": ["NVDA:breadth", "NVDA:company_news"]}


@pytest.fixture(autouse=True)
def models(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setenv("EXPLAINER", "llm")
    monkeypatch.setenv("LLM_ROUTING", "on")
    explainer._CACHE.clear()


# ---- Intake ----------------------------------------------------------------------------

def test_intake_maps_personas_to_bands_and_rrsp_lowers_the_risk():
    assert intake.run("amira")["risk_band"] == "high"
    assert intake.run("mateo")["risk_band"] == "mid"
    assert intake.run("robert")["risk_band"] == "low"
    rrsp = intake.run("amira", "RRSP")
    assert (rrsp["base_risk_band"], rrsp["risk_band"]) == ("high", "mid") and "lowers the risk" in rrsp["account_rule"]
    assert intake.run("robert", "RRSP")["risk_band"] == "low"  # cannot go below the lowest band
    assert intake.run("amira", "TFSA")["risk_band"] == intake.run("amira", "Non-registered")["risk_band"] == "high"


def test_intake_reads_a_self_description_with_the_model_and_validates_it():
    model = Model(text({"risk_band": "low"}))
    out = intake.run(None, message="I'm retired and want safety. Should I sell nvidia?", client=model)
    assert out["risk_band"] == "low" and out["source"] == "model" and out["persona_name"] is None
    assert intake.run(None, message="I'm fine", client=Model(text({"risk_band": "extreme"})))["risk_band"] is None
    assert intake.run(None, message="should I sell nvidia?", client=Model())["risk_band"] is None  # nothing to read, no model call


# ---- Explainer -------------------------------------------------------------------------

def result_for(ticker="NVDA", action="sell"):
    from app.services import sell_guard_service as svc

    market = svc.market_agent(ticker, True)
    return svc.classifier_agent(action, market)["trade_check"]


def test_explainer_output_is_validated_and_cited_against_the_classifiers_ids():
    result = result_for()
    out = explainer.explain("sell", result, None, {"risk_band": "high"}, "en", client=Model(text(GOOD)))
    assert out["source"] == "bedrock" and set(out["evidence_ids"]) <= {e["evidence_id"] for e in result["evidence"]}


def test_explainer_sees_words_never_figures():
    model = Model(text(GOOD))
    explainer.explain("sell", result_for(), None, {"risk_band": "high"}, "en", client=model)
    prompt = json.loads(model.requests[0]["messages"][0]["content"][0]["text"])
    assert not any(ch.isdigit() for ch in json.dumps(prompt["findings"]))
    assert "NVDA:drop" in prompt["allowed_evidence_ids"]


@pytest.mark.parametrize("bad", [
    {**GOOD, "popup_text": "It fell 11 percent."},
    {**GOOD, "detail": "This stock will rise soon."},
    {**GOOD, "evidence_ids": ["NVDA:made_up"]},
    {**GOOD, "evidence_ids": []},
    {**GOOD, "popup_title": ""},
    {**GOOD, "detail": "x" * 900},
])
def test_explainer_rejects_unsafe_text_then_retries_then_gives_up(bad):
    model = Model(text(bad), text(bad), text(bad))
    assert explainer.explain("sell", result_for(), None, {}, "en", client=model) is None
    assert len(model.requests) == 3 and "rejected" in model.requests[1]["messages"][-1]["content"][0]["text"]


def test_explainer_recovers_on_the_corrective_retry_and_caches():
    model = Model(text({**GOOD, "detail": "It fell 11 percent."}), text(GOOD))
    first = explainer.explain("sell", result_for(), None, {}, "en", client=model)
    assert first["detail"] == GOOD["detail"]
    again = explainer.explain("sell", result_for(), None, {}, "en", client=Model())  # no replies left: must hit the cache
    assert again["cached"] is True


def test_french_is_requested_from_the_explainer():
    model = Model(text(GOOD))
    explainer.explain("sell", result_for(), None, {}, "fr", client=model)
    assert "French" in model.requests[0]["system"][0]["text"]


# ---- Pipeline --------------------------------------------------------------------------

def test_pipeline_runs_the_four_agents_in_order_and_passes_evidence_ids_along():
    out = trade_pipeline.run("sell", "NVDA", "amira", None, True, "en", client=Model(text(GOOD)))
    assert [s["agent"] for s in out["trace"]] == ["Intake", "Market", "Classifier", "Explainer"]
    assert out["intake"]["risk_band"] == "high"  # Amira, no account rule
    assert out["trade_check"]["verdict"] == "panic_risk" and out["trade_check"]["driver"] == "market"
    assert out["persona_fit"] and out["position"] and out["explanation"]["popup_title"]
    ids = [e["evidence_id"] for e in out["trade_check"]["evidence"]]
    assert ids[:5] == [f"NVDA:{k}" for k in ("drop", "rise", "volume", "rebound", "breadth")]  # Market's ids come first


def test_the_same_nvidia_sale_is_judged_by_who_is_selling_it():
    run = lambda persona, account=None: trade_pipeline.run("sell", "NVDA", persona, account, True, "en", client=Model(text(GOOD)))
    assert run("amira")["trade_check"]["verdict"] == "panic_risk"  # long horizon, high risk: fear
    # The RRSP lowers the band one step, but NVDA is about 40% of Amira's portfolio: a sale that big needs
    # more evidence, so the concentration keeps it a panic sell.
    rrsp = run("amira", "RRSP")["trade_check"]
    assert rrsp["verdict"] == "panic_risk" and rrsp["profile_adjustment"]["concentration_bias"] > 0
    robert = run("robert")
    assert robert["intake"]["risk_band"] == "low"
    assert robert["trade_check"]["verdict"] == "evidence_supported"  # growth stock, short horizon: fits his plan
    assert robert["trade_check"]["profile_adjustment"]["growth_style"] is True


def test_pipeline_falls_back_to_fixed_wording_when_the_explainer_fails():
    class Down:
        def converse(self, **kw):
            raise RuntimeError("throttled")

    out = trade_pipeline.run("sell", "NVDA", "amira", None, True, "en", client=Down())
    assert out["explanation"] is None and out["trade_check"]["verdict"] == "panic_risk"
    assert "fixed wording" in out["trace"][-1]["action"]


def test_pipeline_needs_the_live_market_and_known_tickers():
    with pytest.raises(LookupError):
        trade_pipeline.run("sell", "NVDA", "amira", None, False, "en", client=Model())
    with pytest.raises(ValueError):
        trade_pipeline.run("sell", "AAPL", "amira", None, True, "en", client=Model())


# ---- Orchestrator routing --------------------------------------------------------------

def test_routing_understands_natural_language_without_keywords():
    model = Model(route("trade_check", action="sell", ticker="Nvidia"), text(GOOD))
    reply = llm_router.run("demo", "is it smart to dump my Nvidia stock?", "en", "amira", True, client=model)
    assert reply["trade_check"]["ticker"] == "NVDA" and reply["answer"] == GOOD["detail"]
    assert [s["agent"] for s in reply["trace"]] == ["Global Orchestrator", "Intake", "Market", "Classifier", "Explainer"]
    assert model.requests[0]["toolConfig"]["toolChoice"] == {"any": {}}  # it must pick a route


def test_routing_hands_other_questions_to_the_rule_based_router():
    assert llm_router.run("demo", "what is a TFSA?", "en", None, False, client=Model(route("other_question"))) is None


def test_routing_greetings_are_checked_for_digits_and_predictions():
    ok = llm_router.run("demo", "hi", "en", None, False, client=Model(route("say", text="Hello! Ask me about a stock.")))
    assert ok["answer"].startswith("Hello") and ok["suggestions"]
    for bad in ("It will rise 5 percent", "stocks will rise soon", ""):
        with pytest.raises(llm_router.RouterError):
            llm_router.run("demo", "hi", "en", None, False, client=Model(route("say", text=bad)))


def test_routing_rejects_invalid_routes_and_outages():
    for bad in (route("trade_check", action="short", ticker="NVDA"), route("trade_check", action="sell", ticker=""), route("delete_all"), text("just text")):
        with pytest.raises(llm_router.RouterError):
            llm_router.run("demo", "x", "en", None, True, client=Model(bad))

    class Down:
        def converse(self, **kw):
            raise RuntimeError("throttled")

    with pytest.raises(llm_router.RouterError):
        llm_router.run("demo", "x", "en", None, True, client=Down())


def test_routing_not_live_asks_for_a_refresh():
    reply = llm_router.run("demo", "sell nvidia?", "en", "amira", False, client=Model(route("trade_check", action="sell", ticker="NVDA")))
    assert "Refresh" in reply["answer"] and reply["trade_check"] is None


# ---- Wired into the agents' entry point -------------------------------------------------

def test_agents_route_with_the_model_and_fall_back_to_rules_when_it_fails(monkeypatch):
    monkeypatch.setattr(bedrock, "client", lambda: Model(route("trade_check", action="sell", ticker="NVDA"), text(GOOD)))
    reply = agent_app.handle("chat", {"message": "ditch nvidia?", "holdings_persona": "amira", "live": True})
    assert reply["trade_check"]["verdict"] == "panic_risk" and reply["trace"][1]["agent"] == "Intake"

    class Down:
        def converse(self, **kw):
            raise RuntimeError("throttled")

    monkeypatch.setattr(bedrock, "client", lambda: Down())
    fallback = agent_app.handle("chat", {"message": "should I sell nvidia", "holdings_persona": "amira", "live": True})
    assert fallback["trade_check"]["verdict"] == "panic_risk"
    assert "rule-based router" in fallback["trace"][1]["action"]


def test_faq_questions_still_reach_the_rule_based_answer(monkeypatch):
    monkeypatch.setattr(bedrock, "client", lambda: Model(route("other_question")))
    reply = agent_app.handle("chat", {"message": "Tell me about recession risk"})
    assert reply["metrics"] and reply["answer"]


def test_account_creation_never_goes_through_the_model(monkeypatch):
    monkeypatch.setattr(bedrock, "client", lambda: (_ for _ in ()).throw(AssertionError("no model for account creation")))
    assert agent_app.handle("chat", {"message": "create a long-term account"})["proposal"]


def test_trade_check_action_returns_the_pipeline_with_its_trace(monkeypatch):
    monkeypatch.setattr(bedrock, "client", lambda: Model(text(GOOD)))
    out = agent_app.handle("trade_check", {"ticker": "NVDA", "action": "sell", "persona": "amira", "account_type": "RRSP", "live": True})
    assert out["explanation"]["popup_text"] and out["intake"]["risk_band"] == "mid"
    assert [s["agent"] for s in out["trace"]] == ["Intake", "Market", "Classifier", "Explainer"]


@pytest.mark.parametrize("advice", [
    "It's important to stay calm before deciding.",
    "You should wait and see what the market does.",
    "Consider the broader trends first.",
    "Vous devriez attendre avant de décider.",
])
def test_explainer_rejects_advice(advice):
    bad = {**GOOD, "detail": advice}
    model = Model(text(bad), text(bad), text(bad))
    assert explainer.explain("sell", result_for(), None, {}, "en", client=model) is None


def test_session_suffix_moves_users_onto_new_code(monkeypatch):
    from app.services import agent_runtime

    monkeypatch.delenv("AGENT_SESSION_SUFFIX", raising=False)  # the developer's .env may set one
    base = agent_runtime._session_id("demo")
    monkeypatch.setenv("AGENT_SESSION_SUFFIX", "-v3")
    assert agent_runtime._session_id("demo") != base and 33 <= len(agent_runtime._session_id("demo")) <= 256
