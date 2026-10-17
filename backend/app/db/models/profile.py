import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import text_enum


class EmployeeProfile(Base):
    """What a person brings to a workspace. Seen only by them and the workspace's managers."""

    __tablename__ = "employee_profiles"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    headline: Mapped[str] = mapped_column(String(150), server_default="")
    summary: Mapped[str] = mapped_column(Text, server_default="")
    # Nullable: unknown until someone states it.
    years_experience: Mapped[int | None] = mapped_column(SmallInteger)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProfileSkill(Base):
    __tablename__ = "profile_skills"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "user_id"],
            ["employee_profiles.workspace_id", "employee_profiles.user_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("workspace_id", "user_id", "name", name="uq_profile_skills_name"),
        CheckConstraint("level BETWEEN 1 AND 5", name="ck_profile_skills_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column()
    user_id: Mapped[uuid.UUID] = mapped_column()
    # Stored as written ("PostgreSQL"); the API refuses duplicates that differ only in case.
    name: Mapped[str] = mapped_column(String(60))
    level: Mapped[int] = mapped_column(SmallInteger)  # 1 beginner … 5 expert


class CvImportStatus(StrEnum):
    QUEUED = "queued"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class CvImport(Base):
    """One run of the CV agent. Holds personal data only as long as needed:
    the CV file until extraction ends, the draft until a manager decides."""

    __tablename__ = "cv_imports"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[CvImportStatus] = mapped_column(
        text_enum(CvImportStatus), server_default=CvImportStatus.QUEUED.value
    )
    size_bytes: Mapped[int] = mapped_column(Integer)
    # Nullable: cleared as soon as the file is deleted from storage.
    storage_key: Mapped[str | None] = mapped_column(String(200))
    # Nullable: filled by the agent, cleared once approved or rejected.
    draft: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    # Nullable: only failed runs have one. A short code, never CV content.
    error_code: Mapped[str | None] = mapped_column(String(50))
    # What the run cost: shown to managers (cost is a first-class metric here).
    model: Mapped[str | None] = mapped_column(String(50))
    cost_usd: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
