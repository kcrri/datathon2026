from __future__ import annotations

from typing import Any, Dict

from app.agents.base import Agent
from app.domain.models import AgentFinding


class DividendStrategyAgent(Agent):
    name = "dividend_strategy_agent"
    role = "Assess the diversified dividend sleeve using observable market data."

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary=(
                "Measure the proposed dividend sleeve's effect on portfolio risk and "
                "diversification; do not treat dividends as guaranteed income."
            ),
            requested_operations=["risk_comparison", "portfolio_snapshot"],
        )
