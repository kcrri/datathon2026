from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from app.domain.models import AgentFinding


class Agent(ABC):
    """Agent boundary: agents plan and interpret; deterministic tools calculate."""

    name = "agent"
    role = ""

    @abstractmethod
    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        raise NotImplementedError
