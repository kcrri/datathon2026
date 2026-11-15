#!/usr/bin/env python3
"""Ask the financial-tools Lambda to classify the simulated headlines with Amazon Bedrock.

    backend/.venv/bin/python scripts/score_news_sentiment.py

The Lambda reads ``<folder>/news.csv`` from the private S3 bucket, scores every headline with
the configured Bedrock model(s) (sentiment -1..1, scope company/market, category), and writes
``<folder>/news_scored.csv`` back to S3. Nothing is classified on this machine; it only sends
the request. Set BEDROCK_VOTE_MODEL_IDS="id1,id2,id3" to vote across several models (the
Lambda takes the median sentiment and majority scope and category, and saves the spread).

Needs AWS_REGION, AWS_PROFILE and LAMBDA_FUNCTION_NAME (backend/.env). Run it only after the
Lambda has been deployed with Bedrock access (see infra/README.md).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    load_dotenv(ROOT / "backend" / ".env")
    function = os.environ["LAMBDA_FUNCTION_NAME"]
    region = os.environ["AWS_REGION"]
    session = boto3.Session(profile_name=os.getenv("AWS_PROFILE"), region_name=region)
    event: dict = {"operation": "score_headlines"}
    models = [m.strip() for m in os.getenv("BEDROCK_VOTE_MODEL_IDS", "").split(",") if m.strip()]
    if models:
        event["model_ids"] = models
    response = session.client("lambda").invoke(
        FunctionName=function, InvocationType="RequestResponse", Payload=json.dumps(event).encode("utf-8")
    )
    result = json.loads(response["Payload"].read())
    if response.get("FunctionError") or result.get("status") != "ok":
        print(f"scoring failed: {result.get('error') or result}", file=sys.stderr)
        return 1
    for folder, info in result["folders"].items():
        print(f"{folder}: {info['headlines']} headlines scored -> {info['written']}")
    agreement = result["scope_agreement"]
    print(f"model scope agrees with the hand label on {agreement['agree']}/{agreement['total']} headlines")
    for item in result["disagreements"]:
        print(f"  models disagree: {item['ticker']} {item['headline'][:60]} (spread {item['spread']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
