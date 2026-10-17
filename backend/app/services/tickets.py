import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, InvalidRequestError, NotFoundError
from app.core.logging import log_fields
from app.db.models import (
    Project,
    ProjectMember,
    ProjectRole,
    Ticket,
    TicketCategory,
    TicketComment,
    TicketStatus,
    TriageTrigger,
    User,
)
from app.schemas.tickets import TicketCreate, TicketUpdate
from app.services import access, assignment_choices, triage_queue
from app.services.embeddings import Embedder

logger = logging.getLogger(__name__)

# Audit logs record that these changed, never their content (it is user text).
_TEXT_FIELDS = frozenset({"title", "description"})
_CLOSED = frozenset({TicketStatus.DONE, TicketStatus.CANCELLED})
# What an employee may change, and only on tickets assigned to them.
_EMPLOYEE_FIELDS = frozenset({"status"})


@dataclass(frozen=True)
class TicketFilters:
    statuses: list[TicketStatus] | None = None
    assignee_id: uuid.UUID | None = None
    unassigned: bool = False
    category: TicketCategory | None = None
    label: str | None = None
    parent_id: uuid.UUID | None = None
    search: str | None = None


async def create_ticket(
    session: AsyncSession,
    project_id: uuid.UUID,
    data: TicketCreate,
    actor: User,
    embedder: Embedder,
) -> Ticket:
    await access.require_manager(session, project_id, actor)
    if data.assignee_id is not None:
        await _check_assignee(session, project_id, data.assignee_id)
    if data.parent_id is not None:
        await _check_parent(session, project_id, None, data.parent_id)
    ticket = Ticket(
        project_id=project_id,
        number=await _next_number(session, project_id),
        reporter_id=actor.id,
        **data.model_dump(),
    )
    await _set_embedding(ticket, embedder)
    session.add(ticket)
    await session.flush()
    # Same transaction: a ticket is never saved without its triage run, or the reverse.
    await triage_queue.enqueue(session, ticket, TriageTrigger.CREATED)
    await session.commit()
    await session.refresh(ticket)
    logger.info(
        "audit.ticket.created",
        extra=log_fields(
            actor=actor.id, project_id=project_id, ticket_id=ticket.id, title_len=len(ticket.title)
        ),
    )
    return ticket


async def copy_ticket(
    session: AsyncSession, ticket_id: uuid.UUID, actor: User, embedder: Embedder
) -> Ticket:
    """A manager reuses a ticket as a template: content and sizing, not the work state."""
    source = await get_ticket(session, ticket_id, actor)
    await access.require_manager(session, source.project_id, actor)
    # Validating rebuilds typed values (e.g. story points) from what the database holds.
    copy = TicketCreate.model_validate(
        {
            "title": f"Copy of {source.title}"[:200],
            "description": source.description,
            "category": source.category,
            "priority": source.priority,
            "labels": source.labels,
            "story_points": source.story_points,
            "parent_id": source.parent_id,
        }
    )
    ticket = await create_ticket(session, source.project_id, copy, actor, embedder)
    logger.info(
        "audit.ticket.copied",
        extra=log_fields(actor=actor.id, source_id=source.id, ticket_id=ticket.id),
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
    session: AsyncSession,
    project_id: uuid.UUID,
    user: User,
    filters: TicketFilters,
    limit: int,
    offset: int,
) -> tuple[list[Ticket], int]:
    await access.project_role(session, project_id, user)
    conditions = [Ticket.project_id == project_id, *_filter_conditions(filters)]
    # id breaks ties so pages never repeat or skip rows with equal timestamps.
    query = select(Ticket).where(*conditions).order_by(Ticket.created_at.desc(), Ticket.id.desc())
    rows = await session.scalars(query.limit(limit).offset(offset))
    total = await session.scalar(select(func.count()).select_from(Ticket).where(*conditions))
    return list(rows), total or 0


async def update_ticket(
    session: AsyncSession,
    ticket_id: uuid.UUID,
    data: TicketUpdate,
    actor: User,
    embedder: Embedder | None,
) -> Ticket:
    ticket = await get_ticket(session, ticket_id, actor)
    role = await access.project_role(session, ticket.project_id, actor)
    changes = data.model_dump(exclude_unset=True)
    if role is ProjectRole.EMPLOYEE:
        _check_employee_change(ticket, changes, actor)
    if changes.get("assignee_id") is not None:
        await _check_assignee(session, ticket.project_id, changes["assignee_id"])
    if changes.get("parent_id") is not None:
        await _check_parent(session, ticket.project_id, ticket.id, changes["parent_id"])
    if changes.get("duplicate_of") is not None:
        await _check_duplicate_target(session, ticket, changes["duplicate_of"])

    before = {name: getattr(ticket, name) for name in changes}
    if changes.get("assignee_id") not in (None, before.get("assignee_id")):
        await assignment_choices.record_choice(session, ticket.id, changes["assignee_id"], actor)
    for name, value in changes.items():
        setattr(ticket, name, value)
    if _TEXT_FIELDS & changes.keys():
        if embedder is None:
            raise RuntimeError("changing title or description needs an embedder")
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


async def return_to_manager(
    session: AsyncSession, ticket_id: uuid.UUID, reason: str, actor: User
) -> Ticket:
    """The assignee hands a ticket back: unassigned, back to To do, reason kept as a comment."""
    ticket = await get_ticket(session, ticket_id, actor)
    if ticket.assignee_id != actor.id:
        raise ForbiddenError("Only the assignee can return this ticket")
    if ticket.status in _CLOSED:
        raise InvalidRequestError("Closed tickets can't be returned")
    ticket.assignee_id = None
    ticket.status = TicketStatus.TODO
    session.add(
        TicketComment(
            ticket_id=ticket.id, author_id=actor.id, body=f"Returned to manager: {reason}"
        )
    )
    await session.commit()
    await session.refresh(ticket)
    logger.info(
        "audit.ticket.returned",
        extra=log_fields(actor=actor.id, ticket_id=ticket.id, reason_len=len(reason)),
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


def _filter_conditions(filters: TicketFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.statuses:
        conditions.append(Ticket.status.in_(filters.statuses))
    if filters.unassigned:
        conditions.append(Ticket.assignee_id.is_(None))
    elif filters.assignee_id is not None:
        conditions.append(Ticket.assignee_id == filters.assignee_id)
    if filters.category is not None:
        conditions.append(Ticket.category == filters.category)
    if filters.label:
        conditions.append(Ticket.labels.contains([filters.label.strip().lower()]))
    if filters.parent_id is not None:
        conditions.append(Ticket.parent_id == filters.parent_id)
    if filters.search:
        # Escape LIKE wildcards so a search for "100%" means the text, not a pattern.
        term = filters.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{term}%"
        matches = or_(
            Ticket.title.ilike(pattern, escape="\\"), Ticket.description.ilike(pattern, escape="\\")
        )
        if filters.search.isdigit():  # "42" also finds PM-42
            matches = or_(matches, Ticket.number == int(filters.search))
        conditions.append(matches)
    return conditions


def _check_employee_change(ticket: Ticket, changes: dict[str, object], actor: User) -> None:
    if changes.keys() - _EMPLOYEE_FIELDS:
        raise ForbiddenError("Only managers can change these fields")
    if ticket.assignee_id != actor.id:
        raise ForbiddenError("Only the assignee can move this ticket")
    if ticket.status in _CLOSED or changes.get("status") in _CLOSED:
        raise ForbiddenError("Only managers can close or reopen tickets")


async def _check_assignee(session: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    is_member = await session.scalar(
        select(
            exists().where(
                and_(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
            )
        )
    )
    if not is_member:
        raise InvalidRequestError("The assignee must be a member of the project")


async def _check_parent(
    session: AsyncSession, project_id: uuid.UUID, ticket_id: uuid.UUID | None, parent_id: uuid.UUID
) -> None:
    """Sub-tasks are one level deep, in the same project."""
    if parent_id == ticket_id:
        raise InvalidRequestError("A ticket can't be its own parent")
    parent = await session.get(Ticket, parent_id)
    if parent is None or parent.project_id != project_id:
        raise InvalidRequestError("The parent must be a ticket in the same project")
    if parent.parent_id is not None:
        raise InvalidRequestError("Sub-tasks can't have sub-tasks")
    if ticket_id is not None:
        has_children = await session.scalar(select(exists().where(Ticket.parent_id == ticket_id)))
        if has_children:
            raise InvalidRequestError("A ticket with sub-tasks can't become a sub-task")


async def _check_duplicate_target(
    session: AsyncSession, ticket: Ticket, target_id: uuid.UUID
) -> None:
    if target_id == ticket.id:
        raise InvalidRequestError("A ticket cannot be a duplicate of itself")
    target = await session.get(Ticket, target_id)
    if target is None or target.project_id != ticket.project_id:
        raise InvalidRequestError("duplicate_of must be a ticket in the same project")


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
