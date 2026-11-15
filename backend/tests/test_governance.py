from __future__ import annotations

from app.agents.governance import GovernanceAgent
from app.domain.models import AnalysisRequest, MetricEvidence


def metric(
    evidence_id: str, current: float, proposed: float
) -> MetricEvidence:
    return MetricEvidence(
        evidence_id=evidence_id,
        label=evidence_id,
        current=current,
        proposed=proposed,
        delta=proposed - current,
        unit="ratio",
        source="fixture",
        formula_version="fixture-v1",
    )


BASE_METRICS = [
    metric("metric.annualized_volatility", 0.18, 0.14),
    metric("metric.maximum_drawdown", -0.20, -0.15),
    metric("metric.annualized_return", 0.30, 0.27),
    metric("metric.concentration_hhi", 0.14, 0.11),
]


def rule_ids(request: AnalysisRequest, metrics=BASE_METRICS) -> set[str]:
    return {
        finding.rule_id
        for finding in GovernanceAgent().evaluate(request, "risk_reduced", metrics)
    }


def test_amira_retains_concentration_control_despite_high_risk_tolerance() -> None:
    concentrated = [
        *BASE_METRICS[:-1],
        metric("metric.concentration_hhi", 0.20, 0.24),
    ]

    assert "CONCENTRATION_CONTROL" in rule_ids(AnalysisRequest(), concentrated)


def test_mateo_reports_missing_esg_evidence() -> None:
    assert "ESG_EVIDENCE_UNAVAILABLE" in rule_ids(
        AnalysisRequest(persona_id="mateo")
    )


def test_robert_default_demo_exposes_short_horizon_conflict() -> None:
    assert "SHORT_HORIZON_PROFILE_CONFLICT" in rule_ids(
        AnalysisRequest(persona_id="robert")
    )


def test_rrsp_scenario_discloses_tax_scope_limit() -> None:
    assert "RRSP_SCOPE_LIMIT" in rule_ids(AnalysisRequest(account_type="RRSP"))
