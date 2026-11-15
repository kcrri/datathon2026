from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


StrategyName = Literal["growth", "dividend", "momentum", "preservation"]
AccountType = Literal["TFSA", "RRSP"]
PersonaId = Literal["amira", "mateo", "robert"]


class StrategyShift(BaseModel):
    from_strategy: StrategyName
    to_strategy: StrategyName
    amount: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def strategies_must_differ(self) -> "StrategyShift":
        if self.from_strategy == self.to_strategy:
            raise ValueError("from_strategy and to_strategy must differ")
        return self


class AnalysisRequest(BaseModel):
    persona_id: PersonaId = "amira"
    question: str = Field(
        default="Would moving 20% of my TFSA from my growth strategy into my dividend strategy reduce my risk?",
        min_length=1,
        max_length=500,
    )
    account_type: AccountType = "TFSA"
    base_currency: Literal["CAD"] = "CAD"
    language: Literal["en", "fr"] = "en"  # language of the written explanation
    strategy_allocations: Dict[StrategyName, float] = Field(
        default_factory=lambda: {
            "growth": 0.60,
            "dividend": 0.20,
            "momentum": 0.10,
            "preservation": 0.10,
        }
    )
    shift: StrategyShift = Field(
        default_factory=lambda: StrategyShift(
            from_strategy="growth", to_strategy="dividend", amount=0.20
        )
    )
    start_date: date = date(2023, 11, 13)
    end_date: date = date(2026, 11, 12)

    @field_validator("strategy_allocations")
    @classmethod
    def allocations_are_valid(
        cls, value: Dict[StrategyName, float]
    ) -> Dict[StrategyName, float]:
        if set(value) != {"growth", "dividend", "momentum", "preservation"}:
            raise ValueError("all four strategy allocations are required")
        if any(weight < 0 or weight > 1 for weight in value.values()):
            raise ValueError("strategy weights must be between 0 and 1")
        if abs(sum(value.values()) - 1.0) > 1e-9:
            raise ValueError("strategy weights must sum to 1")
        return value

    @model_validator(mode="after")
    def scenario_is_possible(self) -> "AnalysisRequest":
        if self.strategy_allocations[self.shift.from_strategy] < self.shift.amount:
            raise ValueError("shift exceeds the source strategy allocation")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must precede end_date")
        return self


class TraceStep(BaseModel):
    step_id: str
    parent_id: str | None = None
    agent: str
    action: str
    status: Literal["completed", "blocked", "failed"] = "completed"
    delegated_to: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class AgentFinding(BaseModel):
    agent: str
    role: str
    summary: str
    requested_operations: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)


class MetricEvidence(BaseModel):
    evidence_id: str
    label: str
    current: float
    proposed: float
    delta: float
    unit: str
    source: str
    formula_version: str


class GovernanceFinding(BaseModel):
    rule_id: str
    severity: Literal["info", "warning", "block"]
    message: str
    evidence_ids: List[str] = Field(default_factory=list)


class Explanation(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    answer: str
    evidence_ids: List[str]
    limitations: List[str] = Field(default_factory=list)
    model_id: str


class PerformancePoint(BaseModel):
    date: date
    current: float
    proposed: float


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    analysis_id: str
    question: str
    persona_id: PersonaId
    account_type: AccountType
    answer: str
    conclusion: Literal["risk_reduced", "risk_increased", "mixed"]
    current_allocations: Dict[str, float]
    proposed_allocations: Dict[str, float]
    metrics: List[MetricEvidence]
    performance_series: List[PerformancePoint]
    agent_findings: List[AgentFinding]
    governance: List[GovernanceFinding]
    trace: List[TraceStep]
    assumptions: List[str]
    limitations: List[str]
    data_sources: List[str]
    model_id: str
    disclaimer: str = (
        "Simulation only. Fictional portfolios. Not financial advice. No real trades."
    )
