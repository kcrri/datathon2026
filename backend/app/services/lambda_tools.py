"""Invoke the real AWS Lambda financial tool. The LLM never calculates metrics."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

import boto3

from app.services.errors import ExternalServiceError, ServiceConfigurationError


def invoke(operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    function_name = os.getenv("LAMBDA_FUNCTION_NAME")
    region = os.getenv("AWS_REGION")
    if not function_name or not region:
        raise ServiceConfigurationError(
            "AWS_REGION and LAMBDA_FUNCTION_NAME are required for financial calculations"
        )

    response = boto3.client("lambda", region_name=region).invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps({"operation": operation, **payload}).encode("utf-8"),
    )
    raw_payload = response["Payload"].read()
    try:
        result = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise ExternalServiceError("financial Lambda returned invalid JSON") from exc

    if response.get("FunctionError") or result.get("status") != "ok":
        error = result.get("error") or response.get("FunctionError") or "unknown error"
        raise ExternalServiceError(f"financial Lambda failed: {error}")
    return result
