import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ErrorResponse
from app.schemas.tickets import (
    SimilarTicket,
    SimilarTickets,
    TicketCreate,
    TicketPage,
    TicketRead,
    TicketUpdate,
)
from app.services import tickets as service
from app.services.embeddings import Embedder, get_embedder

router = APIRouter(tags=["tickets"])

EmbedderDep = Annotated[Embedder, Depends(get_embedder)]

_NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse}}
_NOT_FOUND_OR_CONFLICT: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
}


@router.post(
    "/projects/{project_id}/tickets", status_code=status.HTTP_201_CREATED, responses=_NOT_FOUND
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


@router.get("/projects/{project_id}/tickets", responses=_NOT_FOUND)
async def list_tickets(
    project_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TicketPage:
    tickets, total = await service.list_tickets(session, project_id, user, limit, offset)
    items = [TicketRead.model_validate(t) for t in tickets]
    return TicketPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/tickets/{ticket_id}", responses=_NOT_FOUND)
async def get_ticket(ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> TicketRead:
    return TicketRead.model_validate(await service.get_ticket(session, ticket_id, user))


@router.patch("/tickets/{ticket_id}", responses=_NOT_FOUND)
async def update_ticket(
    ticket_id: uuid.UUID,
    data: TicketUpdate,
    session: SessionDep,
    user: CurrentUser,
    embedder: EmbedderDep,
) -> TicketRead:
    ticket = await service.update_ticket(session, ticket_id, data, user, embedder)
    return TicketRead.model_validate(ticket)


@router.get("/tickets/{ticket_id}/similar", responses=_NOT_FOUND_OR_CONFLICT)
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
