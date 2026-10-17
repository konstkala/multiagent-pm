"""Ticket history, written in the same transaction as the change it describes (ADR 0019)."""

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ticket, TicketEvent, TicketEventKind, User


def record(
    session: AsyncSession,
    ticket: Ticket,
    actor: User | None,
    kind: TicketEventKind,
    before: object = None,
    after: object = None,
) -> None:
    session.add(
        TicketEvent(
            ticket_id=ticket.id,
            project_id=ticket.project_id,
            actor_id=actor.id if actor else None,
            kind=kind,
            from_value=_text(before),
            to_value=_text(after),
        )
    )


def record_changes(
    session: AsyncSession, ticket: Ticket, actor: User, before: Mapping[str, object]
) -> None:
    """Status and assignee moves, compared with the values before an update."""
    for field, kind in (
        ("status", TicketEventKind.STATUS),
        ("assignee_id", TicketEventKind.ASSIGNEE),
    ):
        if field in before and before[field] != getattr(ticket, field):
            record(session, ticket, actor, kind, before[field], getattr(ticket, field))


def _text(value: object) -> str | None:
    # A status (StrEnum) or a user id (UUID): both print as their plain value.
    return None if value is None else str(value)
