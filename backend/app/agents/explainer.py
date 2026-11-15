"""Explainer agent: write the pop-up warning, then the full detail for the chat.

An Amazon Bedrock model (Converse API) writes both texts from the Classifier's findings. It
receives only words (``trade_facts``) and the list of evidence IDs it may cite, never a figure.
Its output is validated before anyone sees it:

* JSON with a pop-up title, a pop-up text, a detail text and the evidence IDs it relies on;
* every cited ID must be one the Classifier produced, and at least one must be cited;
* no digits and no predictions ("will rise", "going to fall"); length limits;
* up to two corrective retries, then ``None``, and the caller falls back to the fixed wording.

The wording is about what the person may be feeling (fear, excitement, the pull of a bargain)
and what the data shows. It never forecasts and never gives advice.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional

from app.agents.trade_facts import evidence_ids, qualitative
from app.i18n import normalize
from app.services.errors import ExternalServiceError

SYSTEM = """You are the explainer of PortfolioGuard AI, a simulation for fictional investors.
You are given findings about a possible buy or sell (words only) and the evidence IDs you may cite.
Write, for a non-technical reader:
- popup_title: at most 8 words naming what the person may be feeling or doing.
- popup_text: two short sentences for a pop-up shown before the trade. Name the likely emotion
  (fear, excitement, the pull of a bargain) and say what the data shows in plain words.
- detail: three or four sentences for the chat. Say what the data shows, what the person may be
  feeling, and how that fits someone with their profile (if an investor note is given).
- evidence_ids: the IDs from the allowed list that support what you wrote (at least one).
Describe; never instruct. Allowed: "Many investments fell together, which can feel frightening."
Not allowed: "It is important to stay calm", "You should wait", "Consider the trends", "Avoid selling".
Write NO digits, percentages or dates. Never predict prices or what will happen next ("will rise" is
not allowed). Never give advice. Use only the supplied findings. Return JSON only:
{"popup_title": "...", "popup_text": "...", "detail": "...", "evidence_ids": ["..."]}"""
FRENCH = "\nWrite every text in Canadian French. The same rules apply."

PREDICTION = re.compile(
    r"\b(will (rise|fall|drop|recover|rebound|go|continue|keep|bounce|increase|decrease)|going to|bound to|"
    r"guarantee[sd]?|sera|seront|vont (monter|baisser|remonter|rebondir))\b",
    re.IGNORECASE,
)
ADVICE = re.compile(
    r"\b(you should|you must|you need to|you ought|it(?:'s| is) important to|i recommend|we recommend|consider|stay calm|"
    r"try to|make sure|avoid|don't|do not|vous devriez|vous devez|il faut|il est important|je recommande|restez|évitez|gardez)\b",
    re.IGNORECASE,
)
LIMITS = {"popup_title": 80, "popup_text": 320, "detail": 800}
_CACHE: Dict[str, Dict[str, Any]] = {}


def enabled() -> bool:
    return os.getenv("EXPLAINER", "llm").strip().lower() == "llm"


def _validate(raw: str, allowed: List[str]) -> Dict[str, Any]:
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        raise ValueError("no JSON in the explanation")
    doc = json.loads(match.group(0))
    out: Dict[str, Any] = {}
    for key, limit in LIMITS.items():
        text = doc.get(key)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{key} is missing")
        text = text.strip()
        if re.search(r"\d", text):
            raise ValueError(f"{key} contains a number")
        if PREDICTION.search(text):
            raise ValueError(f"{key} makes a prediction")
        if ADVICE.search(text):
            raise ValueError(f"{key} gives advice")
        if len(text) > limit:
            raise ValueError(f"{key} is too long")
        out[key] = text
    cited = doc.get("evidence_ids")
    if not isinstance(cited, list) or not cited or not all(isinstance(i, str) for i in cited):
        raise ValueError("the explanation must cite evidence IDs")
    if not set(cited) <= set(allowed):
        raise ValueError("the explanation cited evidence that does not exist")
    out["evidence_ids"] = cited
    return out


def explain(
    action: str,
    result: Dict[str, Any],
    fit: Optional[Dict[str, Any]],
    intake: Dict[str, Any],
    lang: str = "en",
    client: Any = None,
) -> Optional[Dict[str, Any]]:
    """The validated explanation, or None when the model could not produce a valid one."""
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise ExternalServiceError("BEDROCK_MODEL_ID is required for the explainer")
    lang = normalize(lang)
    facts = qualitative(action, result)
    if fit:
        facts["investor"] = {"name": fit["persona"]["name"], "risk_band": intake.get("risk_band"), "goal": fit["persona"]["goal"], "stance": fit["stance"], "note": fit["headline"]}
    allowed = evidence_ids(result)
    key = hashlib.sha256(json.dumps([facts, lang, sorted(allowed)], sort_keys=True).encode()).hexdigest()
    if key in _CACHE:
        return {**_CACHE[key], "cached": True}

    if client is None:
        from app.services import bedrock

        client = bedrock.client()
    system = SYSTEM + (FRENCH if lang == "fr" else "")
    prompt = json.dumps({"findings": facts, "allowed_evidence_ids": allowed}, separators=(",", ":"))
    messages = [{"role": "user", "content": [{"text": prompt}]}]
    explanation: Optional[Dict[str, Any]] = None
    for attempt in range(3):
        try:
            response = client.converse(modelId=model_id, system=[{"text": system}], messages=messages, inferenceConfig={"maxTokens": 500, "temperature": 0.0})
            raw = response["output"]["message"]["content"][0]["text"]
        except Exception as exc:  # throttling, access, timeouts
            raise ExternalServiceError(f"the explainer model call failed: {type(exc).__name__}") from exc
        try:
            explanation = _validate(raw, allowed)
            break
        except (ValueError, json.JSONDecodeError) as exc:
            messages += [
                {"role": "assistant", "content": [{"text": raw}]},
                {"role": "user", "content": [{"text": f"That was rejected: {exc}. Return the JSON again, fixing it. No digits, no predictions, cite only allowed evidence IDs."}]},
            ]
    if explanation is None:
        return None
    explanation = {**explanation, "source": "bedrock", "model_id": model_id}
    if len(_CACHE) > 256:
        _CACHE.clear()
    _CACHE[key] = explanation
    return explanation
