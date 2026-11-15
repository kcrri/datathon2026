"""The selected investor, kept in S3 so every agent and every backend instance sees the same one.

When the person switches investor or account, the agents write a small JSON record to the
private data bucket: ``personas/<user>/current.json`` with the persona, the account and the
risk band the Intake agent derived (account rules applied). Trade checks read it when the
request does not name an investor. Without ``DATA_BUCKET`` (tests, offline work) the record
lives in memory instead.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.agents import intake
from app.domain.presets import ACCOUNT_PRESETS, PERSONAS
from app.services.errors import ExternalServiceError

USER_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")  # becomes part of an S3 key, so no slashes or dots
PREFIX = "personas"
_MEMORY: Dict[str, Dict[str, Any]] = {}
UNSET: Any = object()  # "the caller did not say which profile it had seen"


def _key(user_id: str) -> str:
    if not USER_ID.fullmatch(user_id or ""):
        raise ValueError("user_id may only contain letters, digits, underscore and dash (1 to 64 characters)")
    return f"{os.getenv('INVESTOR_PREFIX', PREFIX).strip('/')}/{user_id}/current.json"


def _client():
    import boto3

    return boto3.client("s3", region_name=os.getenv("AWS_REGION"))


def save(
    user_id: str,
    persona_id: str,
    account_type: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
    known_profile_at: Any = UNSET,
) -> Dict[str, Any]:
    key = _key(user_id)
    if persona_id not in PERSONAS:
        raise ValueError(f"unknown investor: {persona_id}")
    if account_type is not None and account_type not in ACCOUNT_PRESETS:
        raise ValueError(f"unknown account type: {account_type}")
    previous = load(user_id) if (profile is None or known_profile_at is not UNSET) else None
    if known_profile_at is not UNSET and previous and previous.get("profile"):
        # A client saving its own selection says which profile it last saw. If a newer one exists
        # (Claude just sent it), that client is stale: keep the newer profile instead of overwriting it.
        if previous["profile"].get("submitted_at") != known_profile_at:
            return {**previous, "stale_client": True}
    if profile is None and previous and previous.get("persona_id") == persona_id:
        profile = previous.get("profile")  # re-selecting the same investor keeps the submitted profile
    who = intake.run(persona_id, account_type)
    record = {
        "schema": 1,
        "user_id": user_id,
        "persona_id": persona_id,
        "persona_name": who["persona_name"],
        "account_type": account_type,
        "base_risk_band": who["base_risk_band"],
        "risk_band": who["risk_band"],
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if profile:
        record["profile"] = profile
    bucket = os.getenv("DATA_BUCKET")
    if not bucket:
        _MEMORY[key] = record
        return {**record, "stored_in": "memory"}
    try:
        _client().put_object(Bucket=bucket, Key=key, Body=json.dumps(record).encode("utf-8"), ContentType="application/json")
    except Exception as exc:
        raise ExternalServiceError(f"cannot save the investor to s3://{bucket}/{key}: {type(exc).__name__}") from exc
    return {**record, "stored_in": f"s3://{bucket}/{key}"}


def load(user_id: str) -> Optional[Dict[str, Any]]:
    """The saved record, or None when this user has not chosen an investor yet."""
    key = _key(user_id)
    bucket = os.getenv("DATA_BUCKET")
    if not bucket:
        return _MEMORY.get(key)
    try:
        body = _client().get_object(Bucket=bucket, Key=key)["Body"].read()
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code in ("NoSuchKey", "404", "NotFound"):
            return None
        raise ExternalServiceError(f"cannot read the investor from s3://{bucket}/{key}: {type(exc).__name__}") from exc
    try:
        record = json.loads(body)
    except json.JSONDecodeError:
        return None
    # Never trust the stored file beyond what we wrote: it must still name a known investor and account.
    if record.get("persona_id") not in PERSONAS or record.get("account_type") not in (None, *ACCOUNT_PRESETS):
        return None
    return {**record, "stored_in": f"s3://{bucket}/{key}"}


def clear_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """Forget a submitted profile and keep the selected investor."""
    record = load(user_id)
    if not record:
        return None
    record.pop("profile", None)
    record.pop("stored_in", None)
    key, bucket = _key(user_id), os.getenv("DATA_BUCKET")
    if not bucket:
        _MEMORY[key] = record
        return {**record, "stored_in": "memory"}
    try:
        _client().put_object(Bucket=bucket, Key=key, Body=json.dumps(record).encode("utf-8"), ContentType="application/json")
    except Exception as exc:
        raise ExternalServiceError(f"cannot save the investor to s3://{bucket}/{key}: {type(exc).__name__}") from exc
    return {**record, "stored_in": f"s3://{bucket}/{key}"}
