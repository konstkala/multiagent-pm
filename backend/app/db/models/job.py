import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Index, Integer, SmallInteger, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import text_enum


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Job(Base):
    """Background work. The payload holds ids only, never personal data (ADR 0010)."""

    __tablename__ = "jobs"
    __table_args__ = (
        # Workers look for the most urgent, then oldest, runnable job: exactly this index.
        Index("ix_jobs_runnable", "status", "priority", "run_after"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    kind: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    status: Mapped[JobStatus] = mapped_column(
        text_enum(JobStatus), server_default=JobStatus.QUEUED.value
    )
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("3"))
    # Lower runs first, like Unix `nice`: a person waiting on screen beats background work.
    priority: Mapped[int] = mapped_column(SmallInteger, server_default=text("10"))
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Nullable: set while a worker holds the job.
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Nullable: only failed attempts have one. An exception type, never personal data.
    last_error: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
