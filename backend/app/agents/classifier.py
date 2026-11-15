"""Classifier agent: label the move market-driven or company-driven, with scores and sentiment.

Runs in AWS Lambda (operation ``classifier_agent``). It takes the Market agent's output, reads
the headlines (their sentiment pre-scored by Amazon Bedrock), and returns the verdict, the
driver (market, company or mixed), the sentiment label and the fundamental, emotion and hype
scores. Deterministic: the same inputs give the same result. No language model runs here.

The investor's risk band (from Intake: persona plus account rules) sets how big a move must be
before it is flagged: low 2%, mid 3%, high 4% (and a matching volume spike), so a 2% drop can be
a real signal for a cautious RRSP investor and noise for a high-risk one. A growth-style holding
(NVDA) sold by a low-risk, short-horizon investor (Robert) is reasoned, not panic: it does not match his plan.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.services import sell_guard_service


def run(
    action: str, market: Dict[str, Any], risk_band: Optional[str] = None, growth_style: bool = False,
    holding_pct: Optional[float] = None,
) -> Dict[str, Any]:
    return sell_guard_service.classifier_agent(action, market, risk_band, growth_style, holding_pct)
