"""Opt-in acceptance test for the deployed AWS vertical slice.

Run only after an approved deployment:
RUN_AWS_INTEGRATION=1 AWS_PROFILE=... AWS_REGION=... \
LAMBDA_FUNCTION_NAME=... BEDROCK_MODEL_ID=... pytest -m integration -q
"""

from __future__ import annotations

import os

import pytest

from app.agents.orchestrator import GlobalOrchestrator
from app.domain.models import AnalysisRequest


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_AWS_INTEGRATION") != "1",
    reason="set RUN_AWS_INTEGRATION=1 after the AWS deployment is approved",
)
def test_demo_scenario_uses_live_lambda_and_bedrock() -> None:
    required = ["AWS_REGION", "LAMBDA_FUNCTION_NAME", "BEDROCK_MODEL_ID"]
    missing = [name for name in required if not os.getenv(name)]
    assert not missing, f"missing live AWS configuration: {', '.join(missing)}"

    response = GlobalOrchestrator().run(AnalysisRequest())
    steps = {step.step_id: step for step in response.trace}

    assert response.conclusion == "risk_reduced"
    assert response.model_id == os.environ["BEDROCK_MODEL_ID"]
    assert steps["tool.financial_lambda"].details["aws_request_id"] != "unknown"
    assert steps["explainability.synthesize"].evidence_ids
    assert all(source.startswith("s3://") for source in response.data_sources)
