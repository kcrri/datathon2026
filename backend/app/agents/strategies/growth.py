from __future__ import annotations

from typing import Any, Dict

from app.agents.base import Agent
from app.domain.models import AgentFinding


class GrowthStrategyAgent(Agent):
    name = "growth_strategy_agent"
    role = "Assess growth exposure and concentration without forecasting returns."

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary=(
                "Measure how reducing the growth sleeve changes historical volatility, "
                "drawdown, performance, and concentration."
            ),
            requested_operations=["risk_comparison", "performance_comparison"],
        )
