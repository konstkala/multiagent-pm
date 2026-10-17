from datetime import date

from pydantic import BaseModel


class AgentCost(BaseModel):
    runs: int  # runs that made at least one LLM call
    cost_usd: float
    cost_per_run_usd: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None


class FieldAcceptance(BaseModel):
    """What managers did with one suggested field, over accepted runs."""

    field: str
    kept: int  # accepted as suggested
    edited: int  # accepted with a different value
    left_out: int  # not applied


class TriageMetrics(BaseModel):
    runs: int
    accepted: int
    dismissed: int
    failed: int
    waiting: int  # queued, asking a question, or waiting for a decision
    fields: list[FieldAcceptance]
    auto_applied: int  # fields the agent set by itself
    auto_applied_unchanged: int  # of those, still as the agent set them
    cost: AgentCost


class AssignmentMetrics(BaseModel):
    runs: int
    decided: int  # someone was assigned afterwards
    top1_rate: float | None  # of decided runs, the first suggestion was picked
    top3_rate: float | None  # one of the three was picked
    score_p95_ms: float | None
    cost: AgentCost


class AgentMetrics(BaseModel):
    start: date
    end: date
    triage: TriageMetrics
    assignment: AssignmentMetrics
