import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models import AssignmentStatus


class SkillFact(BaseModel):
    name: str
    level: int


class CandidateFacts(BaseModel):
    """The evidence behind a score, shown to the manager and given to the agent."""

    has_profile: bool
    matched_skills: list[SkillFact]  # skills named like one of the ticket's labels
    strongest_skills: list[SkillFact]
    profile_match: float | None  # cosine similarity of ticket and profile
    similar_done: int
    open_points: int
    team_avg_points: float
    overdue: int


class ScoreParts(BaseModel):
    skill: float
    history: float
    availability: float


class Candidate(BaseModel):
    """Stored as JSON in the run and returned as is."""

    user_id: uuid.UUID
    display_name: str
    rank: int
    score: float
    parts: ScoreParts
    facts: CandidateFacts
    reason: str | None  # None until the agent has written it


class AssignmentRunRead(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    status: AssignmentStatus
    candidates: list[Candidate]
    error_code: str | None
    chosen_user_id: uuid.UUID | None
    chosen_rank: int | None  # 1-3, or None if the manager picked someone else
    decided_at: datetime | None
    # Performance and cost, shown next to the suggestions.
    score_ms: float
    model: str | None
    llm_calls: int
    cost_usd: float
    latency_ms: float
    created_at: datetime
    finished_at: datetime | None
