import logging
import uuid
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import ConflictError, InvalidRequestError, NotFoundError
from app.core.logging import log_fields
from app.db.models import LinkType, Ticket, TicketLink, User
from app.services import access
from app.services.tickets import get_ticket

logger = logging.getLogger(__name__)

Direction = Literal["outgoing", "incoming"]


async def list_links(
    session: AsyncSession, ticket_id: uuid.UUID, user: User
) -> list[tuple[TicketLink, Ticket, Direction]]:
    """Both directions: "PM-1 blocks PM-2" shows on PM-1 (outgoing) and on PM-2 (incoming)."""
    await get_ticket(session, ticket_id, user)
    other = aliased(Ticket)
    rows = await session.execute(
        select(TicketLink, other)
        .join(
            other,
            or_(
                (TicketLink.source_id == ticket_id) & (other.id == TicketLink.target_id),
                (TicketLink.target_id == ticket_id) & (other.id == TicketLink.source_id),
            ),
        )
        .order_by(TicketLink.created_at)
    )
    return [
        (link, ticket, "outgoing" if link.source_id == ticket_id else "incoming")
        for link, ticket in rows
    ]


async def add_link(
    session: AsyncSession,
    ticket_id: uuid.UUID,
    target_id: uuid.UUID,
    link_type: LinkType,
    actor: User,
) -> tuple[TicketLink, Ticket]:
    source = await get_ticket(session, ticket_id, actor)
    await access.require_manager(session, source.project_id, actor)
    if target_id == ticket_id:
        raise InvalidRequestError("A ticket can't be linked to itself")
    target = await session.get(Ticket, target_id)
    if target is None or target.project_id != source.project_id:
        raise InvalidRequestError("Links must point to a ticket in the same project")

    link = TicketLink(source_id=ticket_id, target_id=target_id, type=link_type, created_by=actor.id)
    session.add(link)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("These tickets are already linked that way") from exc
    logger.info(
        "audit.ticket.linked",
        extra=log_fields(
            actor=actor.id, source_id=ticket_id, target_id=target_id, type=link_type.value
        ),
    )
    return link, target


async def remove_link(session: AsyncSession, link_id: uuid.UUID, actor: User) -> None:
    link = await session.get(TicketLink, link_id)
    if link is None:
        raise NotFoundError("Link not found")
    try:
        source = await get_ticket(session, link.source_id, actor)
    except NotFoundError as exc:
        raise NotFoundError("Link not found") from exc
    await access.require_manager(session, source.project_id, actor)
    await session.delete(link)
    await session.commit()
    logger.info("audit.ticket.unlinked", extra=log_fields(actor=actor.id, link_id=link_id))
