"""Deterministic governance checks for suitability conflicts and safe boundaries."""

from __future__ import annotations

from app.domain.models import AnalysisRequest, GovernanceFinding, MetricEvidence


class GovernanceAgent:
    name = "governance_agent"

    @staticmethod
    def _proposed_allocations(request: AnalysisRequest) -> dict[str, float]:
        proposed = dict(request.strategy_allocations)
        proposed[request.shift.from_strategy] -= request.shift.amount
        proposed[request.shift.to_strategy] += request.shift.amount
        return proposed

    def evaluate(
        self,
        request: AnalysisRequest,
        conclusion: str,
        metrics: list[MetricEvidence],
    ) -> list[GovernanceFinding]:
        metric_map = {metric.evidence_id: metric for metric in metrics}
        proposed = self._proposed_allocations(request)
        findings = [
            GovernanceFinding(
                rule_id="SIMULATION_ONLY",
                severity="info",
                message=(
                    "This analysis compares fictional portfolios and cannot execute a trade."
                ),
            )
        ]

        if request.account_type == "TFSA":
            findings.append(
                GovernanceFinding(
                    rule_id="TFSA_SCOPE_LIMIT",
                    severity="info",
                    message=(
                        "The scenario does not determine TFSA eligibility, contribution room, "
                        "or tax consequences."
                    ),
                )
            )
        else:
            findings.append(
                GovernanceFinding(
                    rule_id="RRSP_SCOPE_LIMIT",
                    severity="info",
                    message=(
                        "The scenario does not calculate RRSP deduction eligibility, "
                        "withdrawal taxation, or personal tax outcomes."
                    ),
                )
            )

        if conclusion == "risk_reduced":
            findings.append(
                GovernanceFinding(
                    rule_id="RISK_REDUCTION_SUPPORTED",
                    severity="info",
                    message=(
                        "Both annualized volatility and historical maximum drawdown improved "
                        "under the stated methodology."
                    ),
                    evidence_ids=[
                        "metric.annualized_volatility",
                        "metric.maximum_drawdown",
                    ],
                )
            )
        elif conclusion == "mixed":
            findings.append(
                GovernanceFinding(
                    rule_id="MIXED_RISK_EVIDENCE",
                    severity="warning",
                    message="The risk indicators do not move in the same direction.",
                    evidence_ids=[
                        "metric.annualized_volatility",
                        "metric.maximum_drawdown",
                    ],
                )
            )
        else:
            findings.append(
                GovernanceFinding(
                    rule_id="RISK_NOT_REDUCED",
                    severity="warning",
                    message="The proposed shift does not reduce the measured historical risk.",
                    evidence_ids=[
                        "metric.annualized_volatility",
                        "metric.maximum_drawdown",
                    ],
                )
            )

        return_metric = metric_map.get("metric.annualized_return")
        if return_metric and return_metric.delta < 0:
            findings.append(
                GovernanceFinding(
                    rule_id="RETURN_TRADEOFF",
                    severity="info",
                    message=(
                        "The lower measured risk is accompanied by a lower historical annualized return."
                    ),
                    evidence_ids=["metric.annualized_return"],
                )
            )

        if request.persona_id == "mateo":
            findings.append(
                GovernanceFinding(
                    rule_id="ESG_EVIDENCE_UNAVAILABLE",
                    severity="warning",
                    message=(
                        "The starter dataset cannot verify company-level environmental or social controversies."
                    ),
                )
            )

        concentration_metric = metric_map.get("metric.concentration_hhi")
        if (
            request.persona_id == "amira"
            and concentration_metric
            and concentration_metric.proposed > 0.18
        ):
            findings.append(
                GovernanceFinding(
                    rule_id="CONCENTRATION_CONTROL",
                    severity="warning",
                    message=(
                        "The proposed portfolio remains concentrated despite Amira's "
                        "high risk tolerance; diversification controls still apply."
                    ),
                    evidence_ids=["metric.concentration_hhi"],
                )
            )

        if request.persona_id == "mateo" and (
            proposed["growth"] + proposed["momentum"] > 0.60
        ):
            findings.append(
                GovernanceFinding(
                    rule_id="MODERATE_PROFILE_CONFLICT",
                    severity="warning",
                    message=(
                        "The proposed growth and momentum exposure conflicts with Mateo's "
                        "moderate fictional risk profile."
                    ),
                )
            )

        if request.persona_id == "robert" and (
            proposed["growth"] + proposed["momentum"] > 0.40
            or proposed["preservation"] < 0.25
        ):
            findings.append(
                GovernanceFinding(
                    rule_id="SHORT_HORIZON_PROFILE_CONFLICT",
                    severity="warning",
                    message=(
                        "The proposed allocation conflicts with Robert's short fictional "
                        "horizon and capital-preservation objective."
                    ),
                    evidence_ids=[
                        evidence_id
                        for evidence_id in (
                            "metric.annualized_volatility",
                            "metric.maximum_drawdown",
                        )
                        if evidence_id in metric_map
                    ],
                )
            )
        return findings
