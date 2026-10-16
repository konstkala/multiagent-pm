import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ErrorResponse
from app.db.session import get_session
from app.schemas.tickets import TicketCreate, TicketPage, TicketRead, TicketUpdate
from app.services import tickets as service

router = APIRouter(prefix="/tickets", tags=["tickets"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# No authentication yet, so every change is attributed to this placeholder.
ANONYMOUS = "anonymous"

_NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse}}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_ticket(data: TicketCreate, session: SessionDep) -> TicketRead:
    ticket = await service.create_ticket(session, data, actor=ANONYMOUS)
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
    ticket_id: uuid.UUID, data: TicketUpdate, session: SessionDep
) -> TicketRead:
    ticket = await service.update_ticket(session, ticket_id, data, actor=ANONYMOUS)
    return TicketRead.model_validate(ticket)
