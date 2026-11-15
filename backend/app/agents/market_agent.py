"""Market agent: compare the market before and after the refresh and report what changed.

Runs in AWS Lambda (operation ``market_agent``) over the versioned CSVs in Amazon S3: the price
move of the ticker, its volume against the typical level, the rebound, and how many tracked
tickers fell together. Every figure comes back as an evidence item with an ID the next agent
can cite. The refresh itself is the caller's ``live`` flag; nothing is remembered on a server.
"""

from __future__ import annotations

from typing import Any, Dict

from app.services import sell_guard_service


def run(ticker: str, live: bool) -> Dict[str, Any]:
    """Raises LookupError when the market has not been refreshed, ValueError for an unknown ticker."""
    return sell_guard_service.market_agent(ticker, live)
