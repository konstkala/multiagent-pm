import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import text_enum


class TicketEventKind(StrEnum):
    CREATED = "created"
    STATUS = "status"
    ASSIGNEE = "assignee"


class TicketEvent(Base):
    """What happened to a ticket and when: the history KPIs are computed from (ADR 0019)."""

    __tablename__ = "ticket_events"
    __table_args__ = (
        Index("ix_ticket_events_ticket", "ticket_id", "created_at"),
        Index("ix_ticket_events_project_kind", "project_id", "kind", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    # Copied from the ticket (tickets never change project) so dashboards skip a join.
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    # Nullable: the person who did it may since have been deleted.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[TicketEventKind] = mapped_column(text_enum(TicketEventKind))
    # A status or a user id. Nullable: "created" has neither, and unassigning has no new value.
    from_value: Mapped[str | None] = mapped_column(String(40))
    to_value: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
