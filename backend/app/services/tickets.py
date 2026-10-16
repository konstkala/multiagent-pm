import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidRequestError, NotFoundError
from app.core.logging import log_fields
from app.db.models import Ticket
from app.schemas.tickets import TicketCreate, TicketUpdate

logger = logging.getLogger(__name__)

# Audit logs record that these changed, never their content (it is user text).
_TEXT_FIELDS = frozenset({"title", "description"})


async def create_ticket(session: AsyncSession, data: TicketCreate, actor: str) -> Ticket:
    ticket = Ticket(title=data.title, description=data.description)
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    logger.info(
        "audit.ticket.created",
        extra=log_fields(actor=actor, ticket_id=ticket.id, title_len=len(ticket.title)),
    )
    return ticket


async def get_ticket(session: AsyncSession, ticket_id: uuid.UUID) -> Ticket:
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        raise NotFoundError("Ticket not found")
    return ticket


async def list_tickets(session: AsyncSession, limit: int, offset: int) -> tuple[list[Ticket], int]:
    # id breaks ties so pages never repeat or skip rows with equal timestamps.
    query = select(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc())
    rows = await session.scalars(query.limit(limit).offset(offset))
    total = await session.scalar(select(func.count()).select_from(Ticket))
    return list(rows), total or 0


async def update_ticket(
    session: AsyncSession, ticket_id: uuid.UUID, data: TicketUpdate, actor: str
) -> Ticket:
    ticket = await get_ticket(session, ticket_id)
    changes = data.model_dump(exclude_unset=True)
    if "duplicate_of" in changes:
        await _check_duplicate_target(session, ticket_id, changes["duplicate_of"])

    before = {name: getattr(ticket, name) for name in changes}
    for name, value in changes.items():
        setattr(ticket, name, value)
    await session.commit()
    await session.refresh(ticket)

    shown = [name for name in changes if name not in _TEXT_FIELDS]
    logger.info(
        "audit.ticket.updated",
        extra=log_fields(
            actor=actor,
            ticket_id=ticket.id,
            changed_fields=sorted(changes),
            before={name: before[name] for name in shown},
            after={name: getattr(ticket, name) for name in shown},
        ),
    )
    return ticket


async def _check_duplicate_target(
    session: AsyncSession, ticket_id: uuid.UUID, target_id: uuid.UUID | None
) -> None:
    if target_id is None:
        return
    if target_id == ticket_id:
        raise InvalidRequestError("A ticket cannot be a duplicate of itself")
    if await session.get(Ticket, target_id) is None:
        raise InvalidRequestError("duplicate_of does not match an existing ticket")
