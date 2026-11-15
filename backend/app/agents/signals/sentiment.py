"""Sentiment Signal Agent: lets a Bedrock model ask for sentiment instead of hard-coded calls.

The model gets one tool, ``get_ticker_sentiment``. It decides which tickers a question is
about and calls the tool; the tool returns deterministic evidence from the scored headlines
(``sell_guard_service.sentiment_summary``). The model only narrates that evidence: its final
answer must contain no digits, the same rule the explainability agent follows, so it cannot
introduce a number of its own. Every tool call is returned so the UI can show the trace.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from app.services import bedrock, sell_guard_service
from app.services.errors import ExternalServiceError, ServiceConfigurationError

MAX_TOOL_ROUNDS = 3

SYSTEM_PROMPT = """You are the PortfolioGuard AI sentiment assistant for fictional portfolios.
To answer, call get_ticker_sentiment for each ticker the question is about; never guess sentiment.
Then explain in plain words what the news tone looks like and whether related tickers agree.
Use only what the tool returned. Do not write any digits, percentages or dates, do not predict
returns and do not give financial advice. If a ticker has no headlines, say so."""

FRENCH_INSTRUCTION = " Answer in Canadian French. The no-digits rule still applies."

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "get_ticker_sentiment",
                "description": (
                    "Verified news-sentiment evidence for one ticker: headline count, mean and "
                    "recency-weighted sentiment (-1 to 1), related tickers' sentiment and headline categories."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"ticker": {"type": "string", "description": "Ticker, e.g. NVDA or ENB.TO"}},
                        "required": ["ticker"],
                    }
                },
            }
        }
    ]
}


def run_tool(name: str, arguments: Dict[str, Any], live: bool = False) -> Dict[str, Any]:
    """Execute a tool the model asked for. Unknown tools and tickers return an error result."""
    if name != "get_ticker_sentiment":
        return {"error": f"unknown tool: {name}"}
    ticker = str(arguments.get("ticker", "")).strip().upper()
    try:
        return sell_guard_service.sentiment_summary(ticker, live=live)
    except ValueError as exc:
        return {"error": str(exc)}


def ask(question: str, language: str = "en", bedrock_client: Optional[Any] = None, live: bool = False) -> Dict[str, Any]:
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise ServiceConfigurationError("BEDROCK_MODEL_ID is required")
    runtime = bedrock_client or bedrock.client()
    system = SYSTEM_PROMPT + (FRENCH_INSTRUCTION if language == "fr" else "")
    messages: List[Dict[str, Any]] = [{"role": "user", "content": [{"text": question}]}]
    trace: List[Dict[str, Any]] = []

    for _ in range(MAX_TOOL_ROUNDS + 1):
        response = runtime.converse(
            modelId=model_id,
            system=[{"text": system}],
            messages=messages,
            toolConfig=TOOL_CONFIG,
            inferenceConfig={"maxTokens": 500, "temperature": 0.0},
        )
        message = response["output"]["message"]
        messages.append(message)
        calls = [part["toolUse"] for part in message["content"] if "toolUse" in part]
        if not calls:
            answer = "".join(part.get("text", "") for part in message["content"]).strip()
            if not answer:
                raise ExternalServiceError("Bedrock returned no sentiment answer")
            if re.search(r"\d", answer):
                raise ExternalServiceError("Bedrock explanation attempted to introduce a numeric claim")
            return {"answer": answer, "tool_calls": trace, "model_id": model_id}
        results = []
        for call in calls:
            result = run_tool(call["name"], call.get("input", {}), live)
            trace.append({"tool": call["name"], "input": call.get("input", {}), "result": result})
            results.append({"toolResult": {"toolUseId": call["toolUseId"], "content": [{"json": json.loads(json.dumps(result))}]}})
        messages.append({"role": "user", "content": results})
    raise ExternalServiceError("Bedrock kept requesting tools without answering")
