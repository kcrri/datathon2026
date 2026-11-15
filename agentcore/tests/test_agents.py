"""The five AgentCore agents, run in-process with a fake invoker standing in for the runtimes.

The model step is replaced by "call the tool", so these tests check the wiring, the order, the
hand-offs and the persona-aware verdicts, not what a model says. Needs the Strands SDK:
``pip install strands-agents bedrock-agentcore pytest`` and run with ``ENGINE=local``.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("strands")
pytest.importorskip("bedrock_agentcore")

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("ENGINE", "local")
os.environ.pop("DATA_BUCKET", None)
os.environ.pop("BEDROCK_MODEL_ID", None)
sys.path.insert(0, str(ROOT / "agentcore"))
sys.path.insert(0, str(ROOT / "backend"))


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"pg_{name}", ROOT / "agentcore" / name / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # No model in tests: the "agent" simply calls its tool.
    module.run_agent = lambda _n, _s, tools, _p, captured, key: (tools[0](), captured[key])[1]
    return module


AGENTS = {name: load(name) for name in ("intake", "market", "classifier", "explainer", "orchestrator")}
ARNS = {"INTAKE_AGENT_ARN": "intake", "MARKET_AGENT_ARN": "market", "CLASSIFIER_AGENT_ARN": "classifier", "EXPLAINER_AGENT_ARN": "explainer"}
CALLS: list = []


@pytest.fixture(autouse=True)
def runtimes(monkeypatch):
    CALLS.clear()
    for env, name in ARNS.items():
        monkeypatch.setenv(env, f"arn:aws:bedrock-agentcore:us-east-1:000000000000:runtime/{name}")


def fake_invoker(arn: str, request: dict, session: str):
    name = arn.rsplit("/", 1)[-1]
    CALLS.append(name if not request.get("action") else f"{name}:{request['action']}")
    return AGENTS[name].serve(request)


def check(persona: str, ticker: str = "NVDA", account: str | None = None, action: str = "sell", **extra):
    request = {"action": action, "ticker": ticker, "persona": persona, "account_type": account, "live": True, "lang": "en", **extra}
    return AGENTS["orchestrator"].work(request, fake_invoker, use_model=False)


def test_each_agent_is_its_own_runtime_called_in_order():
    out = check("robert")
    assert sorted(CALLS[:2]) == ["intake", "market"]  # Market runs in parallel with Intake
    assert CALLS[2:] == ["classifier", "explainer"]
    assert [s["agent"] for s in out["trace"]] == ["Intake", "Market", "Classifier", "Explainer"]
    assert [s["runtime"] for s in out["trace"]] == ["intake", "market", "classifier", "explainer"]


def test_the_same_sale_is_judged_by_who_is_selling():
    assert check("amira")["verdict"] == "panic_risk"
    assert check("mateo")["verdict"] == "mixed"
    robert = check("robert")
    assert robert["intake"]["risk_band"] == "low" and robert["verdict"] == "evidence_supported"
    assert check("amira", account="RRSP")["verdict"] == "mixed"  # the RRSP lowers the band one step


def test_the_result_has_the_shape_the_app_expects():
    out = check("amira")
    for key in ("verdict", "driver", "evidence", "move_size", "profile_adjustment", "trace", "intake", "explanation"):
        assert key in out
    assert out["persona_fit"]["persona"]["name"] == "Amira"


def test_a_step_run_out_of_order_pulls_in_the_earlier_ones():
    run = AGENTS["orchestrator"].Run({"action": "sell", "ticker": "NVDA", "persona": "robert", "live": True}, fake_invoker)
    run.classify()  # the model jumped straight to the Classifier
    assert sorted(CALLS) == ["classifier", "intake", "market"]
    assert run.finish()["trace"][-1]["agent"] == "Explainer" and CALLS[-1] == "explainer"


def test_a_specialist_failure_reaches_the_caller():
    with pytest.raises(LookupError):  # market not refreshed
        check("amira", live=False)


def test_the_orchestrator_needs_an_action_and_a_ticker():
    common = sys.modules["common"]
    with pytest.raises(common.AgentFailure):
        AGENTS["orchestrator"].work({"ticker": "NVDA"}, fake_invoker, use_model=False)


def test_entrypoints_wrap_results_in_the_envelope():
    reply = AGENTS["market"].invoke({"payload": {"ticker": "NVDA", "live": False}})
    assert reply["ok"] is False and reply["status"] == 409
    reply = AGENTS["market"].invoke({"payload": {"ticker": "NVDA", "live": True}})
    assert reply["ok"] is True and reply["result"]["ticker"] == "NVDA"


# ---- every call goes through the Orchestrator, which routes it to the owning agent ----------

def route(action: str, payload: dict | None = None):
    return AGENTS["orchestrator"].serve({"action": action, "payload": payload or {}}, fake_invoker, use_model=False)


def test_investor_and_account_actions_go_to_intake():
    saved = route("set_investor", {"user_id": "u1", "persona_id": "robert", "account_type": "RRSP"})
    assert saved["risk_band"] == "low" and CALLS == ["intake:set_investor"]
    assert route("get_investor", {"user_id": "u1"})["persona_id"] == "robert"
    assert route("accounts", {"user_id": "u1"}) is not None and CALLS[-1] == "intake:accounts"


def test_analysis_goes_to_the_explainer_and_sentiment_to_the_classifier(monkeypatch):
    # The scenario analysis needs the AWS calculation Lambda and Bedrock, so the owning agent's handler is stubbed.
    monkeypatch.setattr(AGENTS["explainer"], "owned", lambda action, payload: {"answer": "ok", "trace": []})
    monkeypatch.setattr(AGENTS["classifier"], "owned", lambda action, payload: {"answer": "tone", "tool_calls": []})
    out = route("analysis", {"persona_id": "amira"})
    assert CALLS == ["explainer:analysis"] and out["trace"][0]["action"] == "route analysis to the Explainer agent"
    assert route("sentiment_ask", {"question": "how is the news on NVDA?"})["answer"] == "tone"
    assert CALLS[-1] == "classifier:sentiment_ask"


def test_unknown_actions_are_refused():
    common = sys.modules["common"]
    with pytest.raises(common.AgentFailure):
        route("drop_tables")


def test_a_trade_message_in_chat_runs_the_pipeline_and_a_question_goes_to_the_explainer(monkeypatch):
    from app.agents import llm_router

    monkeypatch.setenv("LLM_ROUTING", "on")
    monkeypatch.setattr(llm_router, "_route", lambda *a, **k: {"name": "trade_check", "args": {"action": "sell", "ticker": "NVDA"}})
    reply = route("chat", {"user_id": "u2", "message": "should I dump nvidia?", "holdings_persona": "robert", "live": True, "lang": "en"})
    assert reply["trade_check"]["verdict"] == "evidence_supported"
    assert [s["agent"] for s in reply["trace"]][0] == "Global Orchestrator" and "Classifier" in [s["agent"] for s in reply["trace"]]
    CALLS.clear()
    monkeypatch.setattr(llm_router, "_route", lambda *a, **k: {"name": "other_question", "args": {}})
    route("chat", {"user_id": "u2", "message": "what is a TFSA?", "lang": "en"})
    assert CALLS == ["explainer:knowledge_chat"]


def test_creating_an_account_in_chat_goes_to_intake():
    reply = route("chat", {"user_id": "u3", "message": "open a new account for me", "lang": "en"})
    assert CALLS == ["intake:chat"] and "trace" in reply


# ---- preloading: agents whose answers do not depend on others compute ahead of time --------

def test_preload_warms_market_and_classifier_so_the_click_finds_answers_waiting():
    for module in (AGENTS["market"], AGENTS["classifier"]):
        module._CACHE.clear()
    warmed = route("preload", {"live": True, "user_id": "u4"})
    assert CALLS == ["market:preload", "classifier:preload"]
    assert warmed["market"] and warmed["classifier"]["preloaded"] == warmed["classifier"]["of"] > 0
    out = check("robert")
    steps = {s["agent"]: s["action"] for s in out["trace"]}
    assert steps["Market"].startswith("preloaded answer") and steps["Classifier"].startswith("preloaded answer")
    assert out["verdict"] == "evidence_supported"  # a cached answer is the same answer


def test_preload_needs_the_live_market():
    with pytest.raises(LookupError):
        route("preload", {"live": False})


def test_without_a_preload_the_agents_compute_on_the_click():
    for module in (AGENTS["market"], AGENTS["classifier"]):
        module._CACHE.clear()
    steps = {s["agent"]: s["action"] for s in check("amira")["trace"]}
    assert not steps["Market"].startswith("preloaded") and not steps["Classifier"].startswith("preloaded")
