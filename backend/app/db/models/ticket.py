import uuid
from datetime import date, datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY  # supports @> (contains), unlike the generic one
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import text_enum

EMBEDDING_DIM = 384
STORY_POINTS = (1, 2, 3, 5, 8, 13)  # Fibonacci, ADR 0014


class TicketStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    CANCELLED = "cancelled"


class TicketCategory(StrEnum):
    BUG = "bug"
    IMPLEMENTATION = "implementation"
    IMPROVEMENT = "improvement"
    ANALYSIS = "analysis"
    TASK = "task"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class LinkType(StrEnum):
    BLOCKS = "blocks"
    RELATES_TO = "relates_to"


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        # Cosine distance, the metric these models are trained for.
        Index(
            "ix_tickets_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_tickets_project_status", "project_id", "status"),
        UniqueConstraint("project_id", "number", name="uq_tickets_project_number"),
        CheckConstraint(
            f"story_points IN {STORY_POINTS}", name="ck_tickets_story_points_fibonacci"
        ),
        CheckConstraint("parent_id <> id", name="ck_tickets_not_own_parent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)  # 42 in PM-42, unique within the project
    # Nullable: a deleted account (e.g. a GDPR erasure) must not delete the tickets it reported.
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[TicketStatus] = mapped_column(
        text_enum(TicketStatus), server_default=TicketStatus.TODO.value
    )
    labels: Mapped[list[str]] = mapped_column(ARRAY(String(50)), server_default=text("'{}'"))

    # Nullable on purpose: empty until triage or a manager sets them.
    category: Mapped[TicketCategory | None] = mapped_column(text_enum(TicketCategory))
    priority: Mapped[TicketPriority | None] = mapped_column(text_enum(TicketPriority))
    story_points: Mapped[int | None] = mapped_column(Integer)
    due_date: Mapped[date | None] = mapped_column(Date)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Sub-tasks: one level deep, enforced in the service. Deleting a parent deletes its sub-tasks.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="SET NULL")
    )

    # Nullable: filled when embedding succeeds. The model name travels with the vector because
    # vectors from different models are not comparable.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(String(100))

    # clock_timestamp(), not now(): now() is the transaction start, so rows created in one
    # transaction would tie and list in random order.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TicketLink(Base):
    """A directed relation: `source` blocks / relates to `target`."""

    __tablename__ = "ticket_links"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "type", name="uq_ticket_links"),
        CheckConstraint("source_id <> target_id", name="ck_ticket_links_not_self"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[LinkType] = mapped_column(text_enum(LinkType))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    # Nullable: comments stay when an account is erased; they show as "deleted user".
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    # Nullable: empty until the author edits the comment.
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TicketAttachment(Base):
    """File metadata. The bytes live in object storage under `storage_key`."""

    __tablename__ = "ticket_attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
