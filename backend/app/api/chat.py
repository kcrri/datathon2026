from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent_app import AgentError
from app.domain.models import AnalysisRequest, AnalysisResponse
from app.services import agent_runtime


router = APIRouter()


def _agents(action: str, payload: Dict[str, Any], user_id: str = "demo") -> Any:
    """Run an action in the agent runtime and turn its failures into HTTP errors."""
    try:
        return agent_runtime.call(action, payload, user_id)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


class ChatRequest(BaseModel):
    persona_id: Optional[str] = None
    user_id: str = "demo"
    message: str
    lang: str = "en"
    holdings_persona: Optional[str] = None  # the investor on screen, so trade answers can show their position
    live: bool = False  # the caller's "market refreshed" choice; the server keeps no market state


class ApproveRequest(BaseModel):
    risk: Optional[str] = None
    lang: str = "en"


@router.post("/analysis", response_model=AnalysisResponse)
def analysis(request: AnalysisRequest) -> Any:
    return _agents("analysis", request.model_dump(mode="json"))


@router.post("/chat")
def chat(request: ChatRequest) -> Any:
    """Run the focused analysis or the conversational account flow, in the agent runtime."""
    return _agents("chat", request.model_dump(), request.user_id)


@router.post("/actions/{action_id}/approve")
def approve(action_id: str, request: ApproveRequest) -> Dict[str, Any]:
    return _agents("approve", {"action_id": action_id, "risk": request.risk, "lang": request.lang})


@router.post("/actions/{action_id}/reject")
def reject(action_id: str, lang: str = "en") -> Dict[str, Any]:
    return _agents("reject", {"action_id": action_id, "lang": lang})


@router.get("/accounts")
def accounts(user_id: str = "demo", persona_id: Optional[str] = None, live: bool = False) -> List[Dict[str, Any]]:
    return _agents("accounts", {"user_id": user_id, "persona_id": persona_id, "live": live}, user_id)


@router.delete("/accounts/{account_id}")
def delete_account(account_id: str, user_id: str = "demo") -> Dict[str, bool]:
    return _agents("delete_account", {"user_id": user_id, "account_id": account_id}, user_id)


@router.get("/meta")
def meta() -> Dict[str, Any]:
    from app.agents import knowledge
    from app.profiles import PROFILES

    region = os.getenv("AWS_REGION")
    function_name = os.getenv("LAMBDA_FUNCTION_NAME")
    model_id = os.getenv("BEDROCK_MODEL_ID")
    data_bucket = os.getenv("S3_BUCKET")
    data_prefix = os.getenv("DATA_PREFIX", "starter/v1")

    return {
        "profiles": PROFILES,
        "faq": knowledge.suggestions(),
        "integrations": {
            "region": region,
            "lambda": {
                "configured": bool(region and function_name),
                "label": "AWS Lambda financial tools",
                "detail": function_name or "LAMBDA_FUNCTION_NAME is not configured",
            },
            "bedrock": {
                "configured": bool(region and model_id),
                "label": "Amazon Bedrock explanation",
                "detail": model_id or "BEDROCK_MODEL_ID is not configured",
            },
            "dataset": {
                "configured": bool(region and function_name and data_prefix),
                "label": "Versioned Amazon S3 dataset",
                "detail": (
                    f"s3://{data_bucket}/{data_prefix}/"
                    if data_bucket
                    else f"{data_prefix}/ via Lambda; verified after a successful live run"
                ),
            },
        },
    }
