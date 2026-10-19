import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import SplitStatus


class SubTicketRead(BaseModel):
    title: str
    description: str
    story_points: int


class SplitProposalRead(BaseModel):
    sub_tickets: list[SubTicketRead]
    reason: str
    # What the critic still disliked when the rounds ran out; empty when it was satisfied.
    issues: list[str]
    rounds: int


class SplitCallRead(BaseModel):
    """One LLM call of the graph, so a manager (and a learner) can see where the money went."""

    node: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float
    latency_ms: float


class SplitRunRead(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    status: SplitStatus
    step: str | None  # the graph node that last finished, while it runs
    rounds: int
    proposal: SplitProposalRead | None
    created_ticket_ids: list[uuid.UUID]
    error_code: str | None
    llm_calls: int
    cost_usd: float
    latency_ms: float
    calls: list[SplitCallRead]
    created_at: datetime
    finished_at: datetime | None


class SplitDecision(BaseModel):
    """Indexes (from 0) of the proposed sub-tickets to create. Empty rejects the whole proposal."""

    keep: list[int] = Field(max_length=5)
