"""Reading a ticket's history (the write side is ticket_events.py)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TicketEvent, TicketEventKind, User
from app.schemas.tickets import TicketEventRead
from app.services.tickets import get_ticket

HISTORY_LIMIT = 200


async def history(
    session: AsyncSession, ticket_id: uuid.UUID, user: User, limit: int = HISTORY_LIMIT
) -> list[TicketEventRead]:
    """The ticket's story, oldest first. Any project member may read it."""
    await get_ticket(session, ticket_id, user)
    events = list(
        await session.scalars(
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.created_at)
            .limit(limit)
        )
    )
    wanted = {e.actor_id for e in events if e.actor_id} | {
        uuid.UUID(v)
        for e in events
        if e.kind is TicketEventKind.ASSIGNEE
        for v in (e.from_value, e.to_value)
        if v
    }
    rows = await session.execute(select(User.id, User.display_name).where(User.id.in_(wanted)))
    names = {user_id: name for user_id, name in rows}

    def person(value: str | None) -> str | None:
        return names.get(uuid.UUID(value), "a former member") if value else None

    return [
        TicketEventRead(
            id=e.id,
            kind=e.kind,
            actor_name=names.get(e.actor_id) if e.actor_id else None,
            from_value=person(e.from_value) if e.kind is TicketEventKind.ASSIGNEE else e.from_value,
            to_value=person(e.to_value) if e.kind is TicketEventKind.ASSIGNEE else e.to_value,
            created_at=e.created_at,
        )
        for e in events
    ]
