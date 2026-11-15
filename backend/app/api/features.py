from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import features


router = APIRouter()


class FlagUpdate(BaseModel):
    enabled: bool


@router.get("/features")
def list_features() -> Dict[str, Dict[str, bool]]:
    return {"flags": features.flags()}


@router.put("/features/{feature_id}")
def update_feature(feature_id: str, update: FlagUpdate) -> Dict[str, Dict[str, bool]]:
    try:
        return {"flags": features.set_flag(feature_id, update.enabled)}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown feature: {feature_id}") from None


@router.post("/features/reset")
def reset_features() -> Dict[str, Dict[str, bool]]:
    return {"flags": features.reset()}
