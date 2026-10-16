import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, InvalidRequestError, NotFoundError
from app.core.logging import log_fields
from app.db.models import Project, Ticket, User
from app.schemas.tickets import TicketCreate, TicketUpdate
from app.services import access
from app.services.embeddings import Embedder

logger = logging.getLogger(__name__)

# Audit logs record that these changed, never their content (it is user text).
_TEXT_FIELDS = frozenset({"title", "description"})


async def create_ticket(
    session: AsyncSession,
    project_id: uuid.UUID,
    data: TicketCreate,
    actor: User,
    embedder: Embedder,
) -> Ticket:
    await access.project_role(session, project_id, actor)
    ticket = Ticket(
        project_id=project_id,
        number=await _next_number(session, project_id),
        reporter_id=actor.id,
        title=data.title,
        description=data.description,
    )
    await _set_embedding(ticket, embedder)
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    logger.info(
        "audit.ticket.created",
        extra=log_fields(
            actor=actor.id, project_id=project_id, ticket_id=ticket.id, title_len=len(ticket.title)
        ),
    )
    return ticket


async def get_ticket(session: AsyncSession, ticket_id: uuid.UUID, user: User) -> Ticket:
    """Tickets in projects the user isn't part of don't exist, as far as they can tell."""
    ticket = await session.scalar(
        select(Ticket).where(
            Ticket.id == ticket_id, Ticket.project_id.in_(access.member_projects(user))
        )
    )
    if ticket is None:
        raise NotFoundError("Ticket not found")
    return ticket


async def list_tickets(
    session: AsyncSession, project_id: uuid.UUID, user: User, limit: int, offset: int
) -> tuple[list[Ticket], int]:
    await access.project_role(session, project_id, user)
    in_project = Ticket.project_id == project_id
    # id breaks ties so pages never repeat or skip rows with equal timestamps.
    query = select(Ticket).where(in_project).order_by(Ticket.created_at.desc(), Ticket.id.desc())
    rows = await session.scalars(query.limit(limit).offset(offset))
    total = await session.scalar(select(func.count()).select_from(Ticket).where(in_project))
    return list(rows), total or 0


async def update_ticket(
    session: AsyncSession,
    ticket_id: uuid.UUID,
    data: TicketUpdate,
    actor: User,
    embedder: Embedder,
) -> Ticket:
    ticket = await get_ticket(session, ticket_id, actor)
    changes = data.model_dump(exclude_unset=True)
    if "duplicate_of" in changes:
        await _check_duplicate_target(session, ticket, changes["duplicate_of"])

    before = {name: getattr(ticket, name) for name in changes}
    for name, value in changes.items():
        setattr(ticket, name, value)
    if _TEXT_FIELDS & changes.keys():
        await _set_embedding(ticket, embedder)
    await session.commit()
    await session.refresh(ticket)

    shown = [name for name in changes if name not in _TEXT_FIELDS]
    logger.info(
        "audit.ticket.updated",
        extra=log_fields(
            actor=actor.id,
            ticket_id=ticket.id,
            changed_fields=sorted(changes),
            before={name: before[name] for name in shown},
            after={name: getattr(ticket, name) for name in shown},
        ),
    )
    return ticket


async def find_similar(
    session: AsyncSession, ticket_id: uuid.UUID, user: User, limit: int, min_similarity: float
) -> list[tuple[Ticket, float]]:
    ticket = await get_ticket(session, ticket_id, user)
    if ticket.embedding is None:
        raise ConflictError("This ticket has no embedding yet")

    distance = Ticket.embedding.cosine_distance(ticket.embedding)
    query = (
        select(Ticket, (1 - distance).label("similarity"))
        .where(
            Ticket.id != ticket_id,
            # Never compare across projects: other teams' tickets are not this user's business.
            Ticket.project_id == ticket.project_id,
            # Vectors from different models are not comparable.
            Ticket.embedding_model == ticket.embedding_model,
            distance <= 1 - min_similarity,
        )
        .order_by(distance)
        .limit(limit)
    )
    found = [(row.Ticket, float(row.similarity)) for row in await session.execute(query)]
    logger.info(
        "similar.searched",
        extra=log_fields(
            ticket_id=ticket_id,
            results=len(found),
            top_similarity=round(found[0][1], 3) if found else None,
        ),
    )
    return found


async def _next_number(session: AsyncSession, project_id: uuid.UUID) -> int:
    # One UPDATE ... RETURNING locks the row, so concurrent creates get distinct numbers.
    number = await session.scalar(
        update(Project)
        .where(Project.id == project_id)
        .values(next_ticket_number=Project.next_ticket_number + 1)
        .returning(Project.next_ticket_number - 1)
    )
    if number is None:
        raise NotFoundError("Project not found")
    return number


async def _check_duplicate_target(
    session: AsyncSession, ticket: Ticket, target_id: uuid.UUID | None
) -> None:
    if target_id is None:
        return
    if target_id == ticket.id:
        raise InvalidRequestError("A ticket cannot be a duplicate of itself")
    target = await session.get(Ticket, target_id)
    if target is None or target.project_id != ticket.project_id:
        raise InvalidRequestError("duplicate_of must be a ticket in the same project")


async def _set_embedding(ticket: Ticket, embedder: Embedder) -> None:
    """Embedding is best effort: a ticket must save even if the model is unavailable."""
    text = f"{ticket.title}\n\n{ticket.description}".strip()
    try:
        [vector] = await embedder.embed([text])
    except Exception:  # model files missing, out of memory, bad dimensions...
        logger.exception(
            "embeddings.failed",
            extra=log_fields(ticket_id=ticket.id, model=embedder.model_name, text_len=len(text)),
        )
        # A stale vector would match the old text, so clear it.
        ticket.embedding = None
        ticket.embedding_model = None
        return
    ticket.embedding = vector
    ticket.embedding_model = embedder.model_name
