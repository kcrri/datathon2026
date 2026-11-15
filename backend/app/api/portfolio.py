from __future__ import annotations

import os
import re
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.api.chat import _agents
from app.domain.presets import PERSONAS
from app.services import sell_guard_service
from app.services.errors import ExternalServiceError


router = APIRouter()


def _persona(persona_id: str) -> str:
    if persona_id not in PERSONAS:
        raise HTTPException(status_code=404, detail=f"unknown persona: {persona_id}")
    return persona_id


@router.get("/runtime")
def runtime() -> Dict[str, Any]:
    """Where calculations run right now, proven by a real call (so an outage or expired AWS
    credentials show up here as an error instead of a silent fallback)."""
    status = sell_guard_service.market_status(False)
    sources = status.get("data_sources", [])
    market = next((src for src in sources if "/simulated/" in src), "")
    found = re.match(r"s3://[^/]+/[^/]+/[^/]+", market)  # s3://<bucket>/simulated/v1
    data = found.group(0) if found else os.path.dirname(os.path.dirname(market.split("#")[0]))
    agents = _agents("runtime", {})
    return {
        "agents": agents["agents"],
        "agent_runtime": agents["runtime"],
        "engine": status["computed_by"],
        "function": os.getenv("LAMBDA_FUNCTION_NAME") if status["computed_by"] == "aws-lambda" else None,
        "region": os.getenv("AWS_REGION") if status["computed_by"] == "aws-lambda" else None,
        "data": data,
    }


@router.get("/market")
def market(live: bool = False) -> Dict[str, Any]:
    return sell_guard_service.market_status(live)


def _preload(user_id: str) -> None:
    """Ask the agents to compute the answers that do not depend on who is asking, ahead of the first click."""
    try:
        _agents("preload", {"live": True, "user_id": user_id}, user_id)
    except Exception:  # preloading is an optimisation: a failure just means the click computes it
        pass


@router.post("/market/refresh")
def refresh_market(background: BackgroundTasks, user_id: str = "demo") -> Dict[str, Any]:
    """Load the second dataset (the simulated market change) as the live market.

    Stateless: nothing is remembered on the server. The caller keeps the "live" choice and
    sends ``live=true`` with later requests, so every user and instance behaves the same.
    """
    background.add_task(_preload, user_id)
    return sell_guard_service.market_status(True)


@router.post("/market/reset")
def reset_market() -> Dict[str, Any]:
    return sell_guard_service.market_status(False)


@router.get("/portfolio/{persona_id}")
def portfolio(persona_id: str, account_type: Optional[str] = None, live: bool = False) -> Dict[str, Any]:
    """Holdings for a persona on the current or live market."""
    return sell_guard_service.portfolio(_persona(persona_id), account_type, live)


@router.get("/trade-check/{ticker}")
def trade_check(
    ticker: str,
    action: Literal["buy", "sell"],
    persona: Optional[str] = None,
    lang: str = "en",
    live: bool = False,
    account_type: Optional[str] = None,
    user_id: str = "demo",
) -> Dict[str, Any]:
    """What the market data and news say about buying or selling ``ticker`` (run by the agents).

    With ``persona`` the result also carries what the verdict may feel like for that investor.
    """
    return _agents(
        "trade_check",
        {"ticker": ticker, "action": action, "persona": persona, "lang": lang, "live": live, "account_type": account_type, "user_id": user_id},
        user_id,
    )


@router.get("/sentiment/{ticker}")
def ticker_sentiment(ticker: str, half_life_days: float | None = None, live: bool = False) -> Dict[str, Any]:
    """Sentiment evidence for one ticker (computed in the Lambda; no model call)."""
    try:
        return sell_guard_service.sentiment_summary(ticker.upper(), half_life_days, live)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class SentimentQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    language: Literal["en", "fr"] = "en"
    live: bool = False


@router.post("/sentiment/ask")
def ask_sentiment(body: SentimentQuestion) -> Dict[str, Any]:
    """Bedrock decides which tickers to look up; the evidence still comes from deterministic code."""
    return _agents("sentiment_ask", body.model_dump())


class InvestorChoice(BaseModel):
    persona_id: str
    account_type: Optional[str] = None
    user_id: str = "demo"
    # The profile (by submitted_at) the client last saw; a client that is behind cannot overwrite a newer one.
    known_profile_at: Optional[str] = None


@router.put("/investor")
def set_investor(body: InvestorChoice) -> Dict[str, Any]:
    """Save the selected investor and account to S3 (by the agents), so every agent reads the same one."""
    payload = body.model_dump()
    if "known_profile_at" not in body.model_fields_set:
        payload.pop("known_profile_at")  # an older client that does not say: behave as before
    return _agents("set_investor", payload, body.user_id)


@router.get("/investor")
def get_investor(user_id: str = "demo") -> Dict[str, Any]:
    """The saved investor for this user, or 404 when none has been chosen."""
    record = _agents("get_investor", {"user_id": user_id}, user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="no investor saved for this user")
    return record


@router.delete("/investor/profile")
def clear_investor_profile(user_id: str = "demo") -> Dict[str, Any]:
    """Forget the profile an agent submitted (the selected investor stays)."""
    record = _agents("clear_profile", {"user_id": user_id}, user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="no investor saved for this user")
    return record
