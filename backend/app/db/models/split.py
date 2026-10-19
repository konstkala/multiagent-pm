import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Uuid, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import text_enum


class SplitStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"  # the graph is between steps; `step` says which
    PROPOSED = "proposed"  # the graph is paused at its interrupt, waiting for a manager
    RESUMING = "resuming"  # the manager decided; the worker is finishing the graph
    APPLIED = "applied"
    DISMISSED = "dismissed"
    FAILED = "failed"


class SplitRun(Base):
    """One run of the ticket-splitter graph (ADR 0021). The graph's own resume state lives in
    LangGraph's checkpoint tables, keyed by this row's id; this row is what screens read."""

    __tablename__ = "split_runs"
    __table_args__ = (
        # At most one unfinished run per ticket, like triage_runs.
        Index(
            "uq_split_runs_open",
            "ticket_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running', 'proposed', 'resuming')"),
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
    status: Mapped[SplitStatus] = mapped_column(
        text_enum(SplitStatus), server_default=SplitStatus.QUEUED.value
    )
    # Nullable: only while the graph runs. The node that last finished.
    step: Mapped[str | None] = mapped_column(String(20))
    rounds: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    # Nullable: filled when the graph reaches its interrupt.
    proposal: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Nullable: indexes of the proposed sub-tickets the manager kept (empty means rejected).
    accepted: Mapped[list[int] | None] = mapped_column(JSONB)
    created_ticket_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid[uuid.UUID]()), server_default=text("'{}'")
    )
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    # Nullable: only failed runs have one. A short code, never ticket text.
    error_code: Mapped[str | None] = mapped_column(String(50))
    llm_calls: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cost_usd: Mapped[float] = mapped_column(Float, server_default=text("0"))
    latency_ms: Mapped[float] = mapped_column(Float, server_default=text("0"))
    # One entry per LLM call (node, model, tokens, cost, latency): the UI shows them.
    calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
