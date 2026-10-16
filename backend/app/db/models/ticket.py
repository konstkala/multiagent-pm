import uuid
from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import text_enum

EMBEDDING_DIM = 384


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketType(StrEnum):
    BUG = "bug"
    FEATURE = "feature"
    TASK = "task"
    QUESTION = "question"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


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
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[TicketStatus] = mapped_column(
        text_enum(TicketStatus), server_default=TicketStatus.OPEN.value
    )
    labels: Mapped[list[str]] = mapped_column(ARRAY(String(50)), server_default=text("'{}'"))

    # Nullable on purpose: empty until triage (or a person) sets them.
    type: Mapped[TicketType | None] = mapped_column(text_enum(TicketType))
    priority: Mapped[TicketPriority | None] = mapped_column(text_enum(TicketPriority))
    component: Mapped[str | None] = mapped_column(String(100))
    assignee: Mapped[str | None] = mapped_column(String(100))  # a users table comes later
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="SET NULL")
    )

    # clock_timestamp(), not now(): now() is the transaction start, so rows created in one
    # transaction would tie and list in random order.
    # Nullable: filled when embedding succeeds. The model name travels with the vector because
    # vectors from different models are not comparable.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
