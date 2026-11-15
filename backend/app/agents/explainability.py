"""Evidence-packet construction and grounded Bedrock explanation synthesis."""

from __future__ import annotations

from typing import Callable, Dict

from app.domain.models import Explanation, GovernanceFinding, MetricEvidence
from app.services.bedrock import synthesize


class ExplainabilityAgent:
    name = "explainability_agent"

    def __init__(self, synthesizer: Callable[[Dict], Dict] = synthesize):
        self.synthesizer = synthesizer

    def explain(
        self,
        question: str,
        conclusion: str,
        metrics: list[MetricEvidence],
        governance: list[GovernanceFinding],
        assumptions: list[str],
        limitations: list[str],
        language: str = "en",
    ) -> Explanation:
        allowed_ids = [metric.evidence_id for metric in metrics]
        packet = {
            "question": question,
            "conclusion": conclusion,
            "metrics": [metric.model_dump() for metric in metrics],
            "governance": [finding.model_dump() for finding in governance],
            "assumptions": assumptions,
            "limitations": limitations,
            "allowed_evidence_ids": allowed_ids,
            "language": language,
        }
        return Explanation.model_validate(self.synthesizer(packet))
