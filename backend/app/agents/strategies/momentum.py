from __future__ import annotations

from typing import Any, Dict

from app.agents.base import Agent
from app.domain.models import AgentFinding


class MomentumStrategyAgent(Agent):
    name = "momentum_strategy_agent"
    role = "Describe transparent trailing-price signals without predicting returns."

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary="Retain the unchanged momentum sleeve and disclose its descriptive role.",
            requested_operations=["portfolio_snapshot"],
        )
