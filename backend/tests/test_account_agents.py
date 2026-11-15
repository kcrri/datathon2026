from __future__ import annotations

from app.agents.accounts import RRSPAccountAgent, TFSAAccountAgent
from app.domain.models import AnalysisRequest, StrategyShift


def test_tfsa_delegates_only_to_relevant_strategy_agents() -> None:
    findings = TFSAAccountAgent().delegate(AnalysisRequest())

    assert [finding.agent for finding in findings] == [
        "growth_strategy_agent",
        "dividend_strategy_agent",
    ]


def test_rrsp_delegates_preservation_shift_to_both_relevant_agents() -> None:
    request = AnalysisRequest(
        account_type="RRSP",
        shift=StrategyShift(
            from_strategy="growth", to_strategy="preservation", amount=0.20
        ),
    )

    findings = RRSPAccountAgent().delegate(request)

    assert [finding.agent for finding in findings] == [
        "growth_strategy_agent",
        "capital_preservation_strategy_agent",
    ]
