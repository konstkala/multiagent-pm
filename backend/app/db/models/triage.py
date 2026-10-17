import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import text_enum


class TriageStatus(StrEnum):
    QUEUED = "queued"
    NEEDS_ANSWER = "needs_answer"  # the agent asked the manager a question
    PROPOSED = "proposed"  # waiting for a manager to accept or dismiss
    APPLIED = "applied"
    DISMISSED = "dismissed"
    FAILED = "failed"


class TriageTrigger(StrEnum):
    CREATED = "created"
    MANUAL = "manual"


class TriageRun(Base):
    """One run of the triage agent on a ticket (ADR 0016: state lives here, not in a framework)."""

    __tablename__ = "triage_runs"
    __table_args__ = (
        # At most one unfinished run per ticket: re-running while one is open makes no sense.
        Index(
            "uq_triage_runs_open",
            "ticket_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'needs_answer')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[TriageStatus] = mapped_column(
        text_enum(TriageStatus), server_default=TriageStatus.QUEUED.value
    )
    trigger: Mapped[TriageTrigger] = mapped_column(text_enum(TriageTrigger))
    # Nullable: only when the agent needed to ask, and once the manager has answered.
    question: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    # Nullable: filled when the agent has proposed something.
    proposal: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    auto_applied: Mapped[list[str]] = mapped_column(ARRAY(String(30)), server_default=text("'{}'"))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    # Nullable: only failed runs have one. A short code, never ticket text.
    error_code: Mapped[str | None] = mapped_column(String(50))
    # Totals over every LLM call this run made (a question means two calls).
    model: Mapped[str | None] = mapped_column(String(50))
    llm_calls: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cost_usd: Mapped[float] = mapped_column(Float, server_default=text("0"))
    latency_ms: Mapped[float] = mapped_column(Float, server_default=text("0"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
