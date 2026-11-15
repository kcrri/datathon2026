from __future__ import annotations

import pytest

from app.services.bedrock import _validate_result
from app.services.errors import ExternalServiceError


PACKET = {
    "allowed_evidence_ids": [
        "metric.annualized_volatility",
        "metric.maximum_drawdown",
    ]
}


def test_grounded_explanation_accepts_only_supplied_evidence_ids() -> None:
    result = _validate_result(
        {
            "answer": "Measured historical risk decreased, with future outcomes still uncertain.",
            "evidence_ids": ["metric.annualized_volatility"],
            "limitations": ["Historical observations do not predict future outcomes."],
        },
        PACKET,
        "approved-model",
    )

    assert result["model_id"] == "approved-model"


@pytest.mark.parametrize(
    "document, message",
    [
        (
            {
                "answer": "Volatility fell to 13.7 percent.",
                "evidence_ids": ["metric.annualized_volatility"],
            },
            "numeric claim",
        ),
        (
            {
                "answer": "Measured historical risk decreased.",
                "evidence_ids": ["metric.unsupported"],
            },
            "unsupported evidence",
        ),
    ],
)
def test_explanation_rejects_unsupported_claims(document: dict, message: str) -> None:
    with pytest.raises(ExternalServiceError, match=message):
        _validate_result(document, PACKET, "approved-model")
