import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ErrorResponse
from app.db.session import get_session
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

router = APIRouter(prefix="/tickets", tags=["tickets"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]

# No authentication yet, so every change is attributed to this placeholder.
ANONYMOUS = "anonymous"

_NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse}}
_NOT_FOUND_OR_CONFLICT: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_ticket(
    data: TicketCreate, session: SessionDep, embedder: EmbedderDep
) -> TicketRead:
    ticket = await service.create_ticket(session, data, actor=ANONYMOUS, embedder=embedder)
    return TicketRead.model_validate(ticket)


@router.get("")
async def list_tickets(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TicketPage:
    tickets, total = await service.list_tickets(session, limit, offset)
    items = [TicketRead.model_validate(t) for t in tickets]
    return TicketPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{ticket_id}", responses=_NOT_FOUND)
async def get_ticket(ticket_id: uuid.UUID, session: SessionDep) -> TicketRead:
    return TicketRead.model_validate(await service.get_ticket(session, ticket_id))


@router.patch("/{ticket_id}", responses=_NOT_FOUND)
async def update_ticket(
    ticket_id: uuid.UUID, data: TicketUpdate, session: SessionDep, embedder: EmbedderDep
) -> TicketRead:
    ticket = await service.update_ticket(
        session, ticket_id, data, actor=ANONYMOUS, embedder=embedder
    )
    return TicketRead.model_validate(ticket)


@router.get("/{ticket_id}/similar", responses=_NOT_FOUND_OR_CONFLICT)
async def similar_tickets(
    ticket_id: uuid.UUID,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
    # bge-small scores unrelated text around 0.5, so lower values are noise.
    min_similarity: Annotated[float, Query(ge=0, le=1)] = 0.65,
) -> SimilarTickets:
    found = await service.find_similar(session, ticket_id, limit, min_similarity)
    return SimilarTickets(
        items=[
            SimilarTicket(ticket=TicketRead.model_validate(t), similarity=round(score, 4))
            for t, score in found
        ]
    )
