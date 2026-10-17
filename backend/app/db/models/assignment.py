import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, SmallInteger, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import text_enum


class AssignmentStatus(StrEnum):
    EXPLAINING = "explaining"  # ranked by code; the agent is writing the reasons
    READY = "ready"
    EXPLAIN_FAILED = "explain_failed"  # the ranking still stands, only the reasons are missing


class AssignmentRun(Base):
    """One "Suggest assignee" click: the code's top 3, the agent's reasons, the manager's pick."""

    __tablename__ = "assignment_runs"
    __table_args__ = (
        Index(
            "uq_assignment_runs_explaining",
            "ticket_id",
            unique=True,
            postgresql_where=text("status = 'explaining'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        text_enum(AssignmentStatus), server_default=AssignmentStatus.EXPLAINING.value
    )
    # Ranked candidates with score parts and facts (schemas.assignment.Candidate).
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    score_ms: Mapped[float] = mapped_column(Float)
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    # Nullable: only failed runs have one. A short code, never ticket text.
    error_code: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(50))
    llm_calls: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cost_usd: Mapped[float] = mapped_column(Float, server_default=text("0"))
    latency_ms: Mapped[float] = mapped_column(Float, server_default=text("0"))
    # What the manager did next: the measure of whether the agent helps (hit rate).
    chosen_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # Nullable: 1-3 when the pick was a suggestion, null when it was someone else.
    chosen_rank: Mapped[int | None] = mapped_column(SmallInteger)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
