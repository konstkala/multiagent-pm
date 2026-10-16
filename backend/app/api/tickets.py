import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ErrorResponse
from app.db.models import Ticket, TicketCategory, TicketComment, TicketLink, TicketStatus
from app.schemas.tickets import (
    CommentRead,
    CommentWrite,
    LinkCreate,
    LinkRead,
    ReturnRequest,
    SimilarTicket,
    SimilarTickets,
    TicketBrief,
    TicketCreate,
    TicketPage,
    TicketRead,
    TicketUpdate,
)
from app.services import comments, links
from app.services import tickets as service
from app.services.embeddings import Embedder, get_embedder
from app.services.tickets import TicketFilters

router = APIRouter(tags=["tickets"])

EmbedderDep = Annotated[Embedder, Depends(get_embedder)]

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (403, 404, 409, 422)
}


def _comment(comment: TicketComment, author_name: str | None) -> CommentRead:
    return CommentRead(
        id=comment.id,
        ticket_id=comment.ticket_id,
        author_id=comment.author_id,
        author_name=author_name,
        body=comment.body,
        created_at=comment.created_at,
        edited_at=comment.edited_at,
    )


def _link(link: TicketLink, other: Ticket, direction: str) -> LinkRead:
    return LinkRead(
        id=link.id,
        type=link.type,
        direction="outgoing" if direction == "outgoing" else "incoming",
        ticket=TicketBrief.model_validate(other),
    )


@router.post(
    "/projects/{project_id}/tickets", status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
async def create_ticket(
    project_id: uuid.UUID,
    data: TicketCreate,
    session: SessionDep,
    user: CurrentUser,
    embedder: EmbedderDep,
) -> TicketRead:
    ticket = await service.create_ticket(session, project_id, data, user, embedder)
    return TicketRead.model_validate(ticket)


@router.get("/projects/{project_id}/tickets", responses=_ERRORS)
async def list_tickets(
    project_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    status: Annotated[list[TicketStatus] | None, Query()] = None,
    assignee_id: uuid.UUID | None = None,
    unassigned: bool = False,
    category: TicketCategory | None = None,
    label: Annotated[str | None, Query(max_length=50)] = None,
    parent_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TicketPage:
    filters = TicketFilters(
        statuses=status,
        assignee_id=assignee_id,
        unassigned=unassigned,
        category=category,
        label=label,
        parent_id=parent_id,
        search=q,
    )
    tickets, total = await service.list_tickets(session, project_id, user, filters, limit, offset)
    items = [TicketRead.model_validate(t) for t in tickets]
    return TicketPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/tickets/{ticket_id}", responses=_ERRORS)
async def get_ticket(ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> TicketRead:
    return TicketRead.model_validate(await service.get_ticket(session, ticket_id, user))


@router.patch("/tickets/{ticket_id}", responses=_ERRORS)
async def update_ticket(
    ticket_id: uuid.UUID,
    data: TicketUpdate,
    session: SessionDep,
    user: CurrentUser,
    embedder: EmbedderDep,
) -> TicketRead:
    ticket = await service.update_ticket(session, ticket_id, data, user, embedder)
    return TicketRead.model_validate(ticket)


@router.post("/tickets/{ticket_id}/copy", status_code=status.HTTP_201_CREATED, responses=_ERRORS)
async def copy_ticket(
    ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser, embedder: EmbedderDep
) -> TicketRead:
    return TicketRead.model_validate(await service.copy_ticket(session, ticket_id, user, embedder))


@router.post("/tickets/{ticket_id}/return", responses=_ERRORS)
async def return_to_manager(
    ticket_id: uuid.UUID, data: ReturnRequest, session: SessionDep, user: CurrentUser
) -> TicketRead:
    ticket = await service.return_to_manager(session, ticket_id, data.reason, user)
    return TicketRead.model_validate(ticket)


@router.get("/tickets/{ticket_id}/similar", responses=_ERRORS)
async def similar_tickets(
    ticket_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
    # bge-small scores unrelated text around 0.5, so lower values are noise.
    min_similarity: Annotated[float, Query(ge=0, le=1)] = 0.65,
) -> SimilarTickets:
    found = await service.find_similar(session, ticket_id, user, limit, min_similarity)
    return SimilarTickets(
        items=[
            SimilarTicket(ticket=TicketRead.model_validate(t), similarity=round(score, 4))
            for t, score in found
        ]
    )


@router.get("/tickets/{ticket_id}/comments", responses=_ERRORS)
async def list_comments(
    ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[CommentRead]:
    return [_comment(c, name) for c, name in await comments.list_comments(session, ticket_id, user)]


@router.post(
    "/tickets/{ticket_id}/comments", status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
async def add_comment(
    ticket_id: uuid.UUID, data: CommentWrite, session: SessionDep, user: CurrentUser
) -> CommentRead:
    return _comment(*await comments.add_comment(session, ticket_id, data.body, user))


@router.patch("/comments/{comment_id}", responses=_ERRORS)
async def edit_comment(
    comment_id: uuid.UUID, data: CommentWrite, session: SessionDep, user: CurrentUser
) -> CommentRead:
    return _comment(*await comments.edit_comment(session, comment_id, data.body, user))


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
async def delete_comment(comment_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    await comments.delete_comment(session, comment_id, user)


@router.get("/tickets/{ticket_id}/links", responses=_ERRORS)
async def list_links(
    ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[LinkRead]:
    return [_link(*row) for row in await links.list_links(session, ticket_id, user)]


@router.post("/tickets/{ticket_id}/links", status_code=status.HTTP_201_CREATED, responses=_ERRORS)
async def add_link(
    ticket_id: uuid.UUID, data: LinkCreate, session: SessionDep, user: CurrentUser
) -> LinkRead:
    link, target = await links.add_link(session, ticket_id, data.target_id, data.type, user)
    return _link(link, target, "outgoing")


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
async def remove_link(link_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    await links.remove_link(session, link_id, user)
