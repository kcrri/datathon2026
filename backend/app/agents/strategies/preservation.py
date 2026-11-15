from __future__ import annotations

from typing import Any, Dict

from app.agents.base import Agent
from app.domain.models import AgentFinding


class CapitalPreservationStrategyAgent(Agent):
    name = "capital_preservation_strategy_agent"
    role = "Assess loss sensitivity and stabilizing assets for the stated horizon."

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary="Retain the unchanged preservation sleeve and measure account-level drawdown.",
            requested_operations=["risk_comparison"],
        )
