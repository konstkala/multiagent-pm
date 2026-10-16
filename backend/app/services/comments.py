import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging import log_fields
from app.db.models import ProjectRole, Ticket, TicketComment, User
from app.services import access
from app.services.tickets import get_ticket

logger = logging.getLogger(__name__)

CommentWithAuthor = tuple[TicketComment, str | None]


async def list_comments(
    session: AsyncSession, ticket_id: uuid.UUID, user: User
) -> list[CommentWithAuthor]:
    await get_ticket(session, ticket_id, user)
    rows = await session.execute(
        select(TicketComment, User.display_name)
        .outerjoin(User, User.id == TicketComment.author_id)
        .where(TicketComment.ticket_id == ticket_id)
        .order_by(TicketComment.created_at)
    )
    return [(comment, name) for comment, name in rows]


async def add_comment(
    session: AsyncSession, ticket_id: uuid.UUID, body: str, actor: User
) -> CommentWithAuthor:
    await get_ticket(session, ticket_id, actor)  # any project member may comment
    comment = TicketComment(ticket_id=ticket_id, author_id=actor.id, body=body)
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    logger.info(
        "audit.comment.created",
        extra=log_fields(
            actor=actor.id, ticket_id=ticket_id, comment_id=comment.id, body_len=len(body)
        ),
    )
    return comment, actor.display_name


async def edit_comment(
    session: AsyncSession, comment_id: uuid.UUID, body: str, actor: User
) -> CommentWithAuthor:
    comment, _ = await _comment_for(session, comment_id, actor)
    if comment.author_id != actor.id:
        raise ForbiddenError("You can only edit your own comments")
    comment.body = body
    comment.edited_at = datetime.now(UTC)
    await session.commit()
    logger.info(
        "audit.comment.edited",
        extra=log_fields(actor=actor.id, comment_id=comment.id, body_len=len(body)),
    )
    return comment, actor.display_name


async def delete_comment(session: AsyncSession, comment_id: uuid.UUID, actor: User) -> None:
    comment, ticket = await _comment_for(session, comment_id, actor)
    if comment.author_id != actor.id:
        # Managers may remove anyone's comment, e.g. one that shouldn't be there.
        role = await access.project_role(session, ticket.project_id, actor)
        if role is not ProjectRole.MANAGER:
            raise ForbiddenError("You can only delete your own comments")
    await session.delete(comment)
    await session.commit()
    logger.info(
        "audit.comment.deleted",
        extra=log_fields(actor=actor.id, comment_id=comment_id, ticket_id=ticket.id),
    )


async def _comment_for(
    session: AsyncSession, comment_id: uuid.UUID, user: User
) -> tuple[TicketComment, Ticket]:
    comment = await session.get(TicketComment, comment_id)
    if comment is None:
        raise NotFoundError("Comment not found")
    try:
        ticket = await get_ticket(session, comment.ticket_id, user)
    except NotFoundError as exc:  # comments in projects you can't see don't exist either
        raise NotFoundError("Comment not found") from exc
    return comment, ticket
