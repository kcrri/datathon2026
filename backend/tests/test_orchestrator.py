from __future__ import annotations

import sys
from pathlib import Path

from app.agents.explainability import ExplainabilityAgent
from app.agents.orchestrator import GlobalOrchestrator
from app.domain.models import AnalysisRequest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

from calculations import compare_strategy_shift  # noqa: E402
from data_access import dataset_from_csv_text  # noqa: E402


def test_demo_scenario_has_observable_hierarchical_delegation() -> None:
    source = ROOT / "hackathon_info" / "alphaforge_starter"
    dataset = dataset_from_csv_text(
        (source / "prices_daily.csv").read_text(),
        (source / "fx_usdcad_daily.csv").read_text(),
        sources=["s3://test-bucket/starter/v1/prices_daily.csv#fixture"],
    )

    def financial_tool(operation: str, payload: dict) -> dict:
        assert operation == "compare_strategy_shift"
        result = compare_strategy_shift(payload, dataset)
        result["aws_request_id"] = "fixture-request-id"
        return result

    def synthesizer(packet: dict) -> dict:
        assert packet["conclusion"] == "risk_reduced"
        assert set(packet["allowed_evidence_ids"]) >= {
            "metric.annualized_volatility",
            "metric.maximum_drawdown",
        }
        return {
            "answer": (
                "Yes, the proposed fictional allocation reduced both measured historical "
                "volatility and maximum drawdown, but it also reduced historical return."
            ),
            "evidence_ids": [
                "metric.annualized_volatility",
                "metric.maximum_drawdown",
                "metric.annualized_return",
            ],
            "limitations": ["Future outcomes can differ from this historical comparison."],
            "model_id": "test-bedrock-model",
        }

    response = GlobalOrchestrator(
        financial_tool=financial_tool,
        explainability_agent=ExplainabilityAgent(synthesizer=synthesizer),
    ).run(AnalysisRequest())

    steps = {step.step_id: step for step in response.trace}
    assert response.conclusion == "risk_reduced"
    assert steps["orchestrator.plan"].delegated_to == ["tfsa_account_agent"]
    assert steps["account.delegate"].parent_id == "orchestrator.plan"
    assert steps["account.delegate"].delegated_to == [
        "growth_strategy_agent",
        "dividend_strategy_agent",
    ]
    assert steps["strategy.1"].parent_id == "account.delegate"
    assert steps["strategy.2"].parent_id == "account.delegate"
    assert steps["tool.financial_lambda"].parent_id == "account.delegate"
    assert steps["tool.financial_lambda"].details["aws_request_id"] == "fixture-request-id"
    assert steps["explainability.synthesize"].details["model_id"] == "test-bedrock-model"
    assert response.proposed_allocations["growth"] == 0.4
    assert response.proposed_allocations["dividend"] == 0.4
