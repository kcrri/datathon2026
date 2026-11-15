"""Grounded explanation synthesis through the real Amazon Bedrock Converse API."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

import boto3

from app.services.errors import ExternalServiceError, ServiceConfigurationError


FRENCH_INSTRUCTION = (
    "\nWrite the answer and every limitation in Canadian French. "
    "The no-digits rule still applies: spell out any quantity or use none."
)

SYSTEM_PROMPT = """You are the PortfolioGuard AI explainability component.
Use only the supplied evidence. Do not calculate or repeat numeric figures, percentages, dates,
or numbers from the user's question. The answer must contain no digits. Do not predict returns,
expose hidden reasoning, or provide financial advice. The dashboard displays all verified
numbers separately. Return JSON only with this shape:
{"answer": "concise answer with the material risk/return trade-off", "evidence_ids":
["only supplied evidence IDs"], "limitations": ["material limitations"]}.
The answer must distinguish historical observations from future outcomes.
"""


def client():
    region = os.getenv("AWS_REGION")
    if not region:
        raise ServiceConfigurationError("AWS_REGION is required for Amazon Bedrock")
    return boto3.client("bedrock-runtime", region_name=region)


def _extract_json(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```")
        cleaned = cleaned.removesuffix("```").strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ExternalServiceError("Bedrock returned an invalid explanation document") from exc
    if not isinstance(value, dict):
        raise ExternalServiceError("Bedrock explanation must be a JSON object")
    return value


def _validate_result(
    result: Dict[str, Any], evidence_packet: Dict[str, Any], model_id: str
) -> Dict[str, Any]:
    allowed_ids = set(evidence_packet["allowed_evidence_ids"])
    answer = result.get("answer")
    cited_ids = result.get("evidence_ids")
    if not isinstance(answer, str) or not answer.strip():
        raise ExternalServiceError("Bedrock explanation is missing an answer")
    if re.search(r"\d", answer):
        raise ExternalServiceError(
            "Bedrock explanation attempted to introduce a numeric claim"
        )
    if (
        not isinstance(cited_ids, list)
        or not cited_ids
        or not all(isinstance(item, str) for item in cited_ids)
    ):
        raise ExternalServiceError("Bedrock explanation must cite evidence")
    if not set(cited_ids).issubset(allowed_ids):
        raise ExternalServiceError("Bedrock explanation cited unsupported evidence")
    limitations = result.get("limitations", [])
    if not isinstance(limitations, list):
        raise ExternalServiceError("Bedrock limitations must be a list")
    return {
        "answer": answer.strip(),
        "evidence_ids": cited_ids,
        "limitations": [str(item) for item in limitations],
        "model_id": model_id,
    }


def synthesize(evidence_packet: Dict[str, Any]) -> Dict[str, Any]:
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise ServiceConfigurationError("BEDROCK_MODEL_ID is required")

    prompt = "Explain this verified evidence packet:\n" + json.dumps(
        evidence_packet, separators=(",", ":")
    )
    messages = [{"role": "user", "content": [{"text": prompt}]}]

    def request() -> str:
        response = client().converse(
            modelId=model_id,
            system=[{"text": SYSTEM_PROMPT + (FRENCH_INSTRUCTION if evidence_packet.get("language") == "fr" else "")}],
            messages=messages,
            inferenceConfig={"maxTokens": 500, "temperature": 0.0},
        )
        try:
            return response["output"]["message"]["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError(
                "Bedrock response did not contain explanation text"
            ) from exc

    text = request()
    try:
        result = _validate_result(_extract_json(text), evidence_packet, model_id)
    except ExternalServiceError as exc:
        if str(exc) != "Bedrock explanation attempted to introduce a numeric claim":
            raise
        messages.extend(
            [
                {"role": "assistant", "content": [{"text": text}]},
                {
                    "role": "user",
                    "content": [
                        {
                            "text": (
                                "The previous answer violated the no-numbers rule. "
                                "Return the same JSON answer without any digits, "
                                "percentages, dates, or numeric words."
                            )
                        }
                    ],
                },
            ]
        )
        result = _validate_result(_extract_json(request()), evidence_packet, model_id)

    return result
