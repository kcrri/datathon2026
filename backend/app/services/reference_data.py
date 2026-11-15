"""Read the starter reference files (macro rates, asset universe).

Deployed, they come from the private S3 bucket (``DATA_BUCKET`` / ``DATA_PREFIX``), so the agent
runtime needs no local files. Without ``DATA_BUCKET`` the same files are read from the repo's
starter folder, which is only for tests and offline work.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from app.services.errors import ExternalServiceError


def _local_dir() -> Optional[Path]:
    override = os.getenv("MACRO_DATA_DIR")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    return here.parents[3] / "hackathon_info" / "alphaforge_starter" if len(here.parents) > 3 else None


def read_text(name: str) -> str:
    bucket = os.getenv("DATA_BUCKET")
    if bucket:
        import boto3

        key = f"{os.getenv('DATA_PREFIX', 'starter/v1').strip('/')}/{name}"
        try:
            body = boto3.client("s3", region_name=os.getenv("AWS_REGION")).get_object(Bucket=bucket, Key=key)["Body"]
            return body.read().decode("utf-8")
        except Exception as exc:  # botocore ClientError and friends
            raise ExternalServiceError(f"cannot read s3://{bucket}/{key}") from exc
    directory = _local_dir()
    if directory is None or not (directory / name).is_file():
        raise FileNotFoundError(name)
    return (directory / name).read_text(encoding="utf-8")
