import uuid
from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ErrorResponse
from app.db.models import TriageRun
from app.schemas.triage import TriageAccept, TriageAnswer, TriageProposalRead, TriageRunRead
from app.services import triage

router = APIRouter(tags=["triage"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (403, 404, 409, 422)
}


def _read(run: TriageRun) -> TriageRunRead:
    return TriageRunRead(
        id=run.id,
        ticket_id=run.ticket_id,
        status=run.status,
        trigger=run.trigger,
        question=run.question,
        answer=run.answer,
        proposal=TriageProposalRead.model_validate(run.proposal) if run.proposal else None,
        auto_applied=run.auto_applied,
        error_code=run.error_code,
        model=run.model,
        llm_calls=run.llm_calls,
        cost_usd=run.cost_usd,
        latency_ms=run.latency_ms,
        created_at=run.created_at,
        finished_at=run.finished_at,
    )


@router.get("/tickets/{ticket_id}/triage", responses=_ERRORS)
async def latest_triage(
    ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> TriageRunRead | None:
    run = await triage.latest(session, ticket_id, user)
    return _read(run) if run else None


@router.post("/tickets/{ticket_id}/triage", status_code=status.HTTP_202_ACCEPTED, responses=_ERRORS)
async def rerun_triage(
    ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> TriageRunRead:
    return _read(await triage.rerun(session, ticket_id, user))


@router.post("/triage-runs/{run_id}/answer", responses=_ERRORS)
async def answer_triage(
    run_id: uuid.UUID, data: TriageAnswer, session: SessionDep, user: CurrentUser
) -> TriageRunRead:
    return _read(await triage.answer(session, run_id, data.answer, user))


@router.post("/triage-runs/{run_id}/accept", responses=_ERRORS)
async def accept_triage(
    run_id: uuid.UUID, data: TriageAccept, session: SessionDep, user: CurrentUser
) -> TriageRunRead:
    return _read(await triage.accept(session, run_id, data, user))


@router.post("/triage-runs/{run_id}/dismiss", responses=_ERRORS)
async def dismiss_triage(
    run_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> TriageRunRead:
    return _read(await triage.dismiss(session, run_id, user))
