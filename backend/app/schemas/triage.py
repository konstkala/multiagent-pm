import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import TicketCategory, TicketPriority, TriageStatus, TriageTrigger
from app.schemas.tickets import Labels, StoryPoints


class TriageProposalRead(BaseModel):
    category: TicketCategory
    labels: list[str]
    priority: TicketPriority
    story_points: int
    duplicate_of: int | None  # the ticket number, as the agent saw it
    duplicate_of_id: uuid.UUID | None
    duplicate_of_title: str | None
    classification_confidence: float
    sizing_confidence: float
    reason: str


class TriageRunRead(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    status: TriageStatus
    trigger: TriageTrigger
    question: str | None
    answer: str | None
    proposal: TriageProposalRead | None
    auto_applied: list[str]  # fields the agent set by itself
    error_code: str | None
    # What the run cost in total (a question means two calls).
    model: str | None
    llm_calls: int
    cost_usd: float
    latency_ms: float
    created_at: datetime
    finished_at: datetime | None


class TriageAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=2_000)


class TriageAccept(BaseModel):
    """The fields the manager keeps, possibly edited. Only the fields sent are applied."""

    category: TicketCategory | None = None
    labels: Labels | None = None
    priority: TicketPriority | None = None
    story_points: StoryPoints | None = None
    duplicate_of: uuid.UUID | None = None
