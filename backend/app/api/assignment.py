import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ErrorResponse
from app.db.models import AssignmentRun
from app.schemas.assignment import AssignmentRunRead
from app.services import assignment
from app.services.embeddings import Embedder, get_embedder

router = APIRouter(tags=["assignment"])

EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (403, 404, 409)
}


def _read(run: AssignmentRun) -> AssignmentRunRead:
    return AssignmentRunRead.model_validate(run, from_attributes=True)


@router.get("/tickets/{ticket_id}/assignment-suggestions", responses=_ERRORS)
async def latest_suggestions(
    ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> AssignmentRunRead | None:
    run = await assignment.latest(session, ticket_id, user)
    return _read(run) if run else None


@router.post(
    "/tickets/{ticket_id}/assignment-suggestions",
    status_code=status.HTTP_202_ACCEPTED,
    responses=_ERRORS,
)
async def suggest_assignees(
    ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser, embedder: EmbedderDep
) -> AssignmentRunRead:
    """Ranked at once; the reasons follow from a background job (poll the GET)."""
    return _read(await assignment.suggest(session, ticket_id, user, embedder))
