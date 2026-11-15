"""Intake agent: turn who is asking into a low, mid or high risk persona and apply the account rules.

The investor's persona preset gives the starting risk band (low, mid or high). The account rules
then adjust it: an RRSP lowers the risk one step; TFSA and non-registered accounts leave it as is.
When no persona is selected but the message describes the investor ("I'm retired and want safety"),
an Amazon Bedrock model reads the description and picks the band; its answer is validated and a
failure simply means "no persona". Tools: Amazon Bedrock (LLM), persona and risk presets.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

from app.domain.presets import PERSONAS
from app.i18n import normalize, pick

BANDS = ("low", "mid", "high")
PRESET_BAND = {"high": "high", "moderate": "mid", "low-moderate": "low"}
RULES = {  # account type -> how it moves the band
    "RRSP": -1,
    "TFSA": 0,
    "Non-registered": 0,
}
SELF_DESCRIPTION = re.compile(
    r"\b(i am|i'm|im|my age|years old|retired|retire|conservative|aggressive|cautious|risk|beginner|"
    r"je suis|ans|retraité|prudent|agressif)\b",
    re.IGNORECASE,
)
SYSTEM = """You read how an investor describes themselves and pick a risk band.
Return JSON only: {"risk_band": "low" | "mid" | "high" | "unknown"}.
low: wants safety and preserving capital, or is close to needing the money.
mid: wants balanced growth with stability.
high: long horizon, comfortable with large swings.
Use "unknown" when the message says nothing about the person. No explanation."""


def _shift(band: str, delta: int) -> str:
    return BANDS[max(0, min(len(BANDS) - 1, BANDS.index(band) + delta))]


def infer_from_text(message: str, client: Any = None) -> Optional[str]:
    """Ask Bedrock for the band a self-description implies; None when it says nothing or fails."""
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id or not SELF_DESCRIPTION.search(message):
        return None
    try:
        if client is None:
            from app.services import bedrock

            client = bedrock.client()
        response = client.converse(
            modelId=model_id,
            system=[{"text": SYSTEM}],
            messages=[{"role": "user", "content": [{"text": message}]}],
            inferenceConfig={"maxTokens": 40, "temperature": 0.0},
        )
        text = response["output"]["message"]["content"][0]["text"]
        band = json.loads(re.search(r"\{.*\}", text, re.S).group(0)).get("risk_band")
    except Exception:  # unreadable, throttled or invalid: treat as no description
        return None
    return band if band in BANDS else None


def run(
    persona_id: Optional[str],
    account_type: Optional[str] = None,
    message: Optional[str] = None,
    lang: str = "en",
    client: Any = None,
    allow_model: bool = True,
) -> Dict[str, Any]:
    lang = normalize(lang)
    persona = PERSONAS.get(persona_id or "")
    if persona:
        base, source = PRESET_BAND[persona["risk"]], "preset"
    elif allow_model and message and (inferred := infer_from_text(message, client)):
        base, source = inferred, "model"
    else:
        return {"agent": "Intake", "persona_id": None, "persona_name": None, "base_risk_band": None, "risk_band": None, "account_type": account_type, "account_rule": None, "source": None}

    delta = RULES.get(account_type or "", 0)
    band = _shift(base, delta)
    rule = None
    if account_type == "RRSP":
        rule = pick(lang, "RRSP lowers the risk one step" if band != base else "RRSP lowers the risk (already at the lowest band)", "Le REER abaisse le risque d'un cran" if band != base else "Le REER abaisse le risque (déjà au niveau le plus bas)")
    return {
        "agent": "Intake",
        "persona_id": persona_id if persona else None,
        "persona_name": persona["name"] if persona else None,
        "base_risk_band": base,
        "risk_band": band,
        "account_type": account_type,
        "account_rule": rule,
        "source": source,
    }
