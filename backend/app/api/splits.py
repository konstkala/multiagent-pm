import uuid
from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ErrorResponse
from app.db.models import SplitRun
from app.schemas.splits import SplitCallRead, SplitDecision, SplitProposalRead, SplitRunRead
from app.services import splits

router = APIRouter(tags=["splits"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (403, 404, 409, 422)
}


def _read(run: SplitRun) -> SplitRunRead:
    return SplitRunRead(
        id=run.id,
        ticket_id=run.ticket_id,
        status=run.status,
        step=run.step,
        rounds=run.rounds,
        proposal=SplitProposalRead.model_validate(run.proposal) if run.proposal else None,
        created_ticket_ids=run.created_ticket_ids,
        error_code=run.error_code,
        llm_calls=run.llm_calls,
        cost_usd=run.cost_usd,
        latency_ms=run.latency_ms,
        calls=[SplitCallRead.model_validate(call) for call in run.calls],
        created_at=run.created_at,
        finished_at=run.finished_at,
    )


@router.get("/tickets/{ticket_id}/split", responses=_ERRORS)
async def latest_split(
    ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> SplitRunRead | None:
    run = await splits.latest(session, ticket_id, user)
    return _read(run) if run else None


@router.post("/tickets/{ticket_id}/split", status_code=status.HTTP_202_ACCEPTED, responses=_ERRORS)
async def request_split(
    ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> SplitRunRead:
    return _read(await splits.request_split(session, ticket_id, user))


@router.post("/split-runs/{run_id}/decide", status_code=status.HTTP_202_ACCEPTED, responses=_ERRORS)
async def decide_split(
    run_id: uuid.UUID, data: SplitDecision, session: SessionDep, user: CurrentUser
) -> SplitRunRead:
    return _read(await splits.decide(session, run_id, data.keep, user))
