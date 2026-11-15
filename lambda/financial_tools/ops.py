"""Operation dispatcher shared by the Lambda handler and the backend's local engine.

``run`` takes the request event plus the stores (S3 when deployed) and returns a JSON-able
result with ``status: "ok"``. ``computed_by`` says where the numbers were produced.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional

try:
    from . import market_store, market_tools, news_scoring
except ImportError:  # Lambda CodeUri places modules at the runtime root.
    import market_store
    import market_tools
    import news_scoring

MARKET_OPERATIONS = (
    "market_status", "portfolio_snapshot", "trade_check", "sentiment_summary", "score_headlines",
    "market_agent", "classifier_agent", "investor_position", "account_values",
)


def _model_ids(event: Dict[str, Any]) -> list:
    configured = event.get("model_ids") or os.getenv("BEDROCK_VOTE_MODEL_IDS", "")
    ids = configured if isinstance(configured, list) else [m.strip() for m in str(configured).split(",") if m.strip()]
    return ids or [m for m in [os.getenv("BEDROCK_MODEL_ID")] if m]


def run(
    event: Dict[str, Any],
    stores: market_store.MarketStores,
    bedrock_client: Optional[Any] = None,
    computed_by: str = "aws-lambda",
) -> Dict[str, Any]:
    operation = event.get("operation")
    if operation == "score_headlines":
        if bedrock_client is None:
            import boto3
            from botocore.config import Config

            bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=os.getenv("AWS_REGION", "us-east-1"),
                config=Config(retries={"max_attempts": 6, "mode": "adaptive"}, read_timeout=60),
            )
        result = news_scoring.score_market_news(
            stores, bedrock_client, _model_ids(event), event.get("folders") or market_store.FOLDERS
        )
    elif operation in MARKET_OPERATIONS:
        data = market_store.load_market(stores)
        handlers: Dict[str, Callable[[Any, Any], Dict[str, Any]]] = {
            "market_status": lambda d, e: market_tools.market_status(d, bool(e.get("live"))),
            "portfolio_snapshot": market_tools.portfolio_snapshot,
            "trade_check": market_tools.trade_check,
            "sentiment_summary": market_tools.sentiment_summary,
            "market_agent": market_tools.market_agent,
            "classifier_agent": market_tools.classifier_agent,
            "investor_position": market_tools.investor_position,
            "account_values": market_tools.account_values,
        }
        result = handlers[operation](data, event)
        result["data_sources"] = data["sources"]
    else:
        raise ValueError(f"unsupported operation: {operation}")
    return {"status": "ok", "operation": operation, "computed_by": computed_by, **result}
