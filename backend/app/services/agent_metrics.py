"""How the agents perform: quality (what managers kept), cost and speed. Managers only."""

import logging
import time
import typing
import uuid
from datetime import UTC, date, datetime, timedelta
from datetime import time as day_start
from typing import Any

from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import log_fields
from app.db.models import AssignmentRun, Ticket, TriageRun, TriageStatus, User
from app.schemas.agent_metrics import (
    AgentCost,
    AgentMetrics,
    AssignmentMetrics,
    FieldAcceptance,
    TriageMetrics,
)
from app.services import access

logger = logging.getLogger(__name__)

SUGGESTED_FIELDS = ("category", "labels", "priority", "story_points")
_WAITING = (TriageStatus.QUEUED, TriageStatus.NEEDS_ANSWER, TriageStatus.PROPOSED)

RunModel = type[TriageRun] | type[AssignmentRun]


async def agent_metrics(
    session: AsyncSession, project_id: uuid.UUID, actor: User, start: date, end: date
) -> AgentMetrics:
    await access.require_manager(session, project_id, actor)
    started = time.perf_counter()
    since = datetime.combine(start, day_start.min, UTC)
    until = datetime.combine(end + timedelta(days=1), day_start.min, UTC)
    metrics = AgentMetrics(
        start=start,
        end=end,
        triage=await _triage(session, project_id, since, until),
        assignment=await _assignment(session, project_id, since, until),
    )
    logger.info(
        "agent_metrics.computed",
        extra=log_fields(
            project_id=project_id,
            range_days=(end - start).days + 1,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        ),
    )
    return metrics


async def _triage(
    session: AsyncSession, project_id: uuid.UUID, since: datetime, until: datetime
) -> TriageMetrics:
    rows = (
        await session.execute(
            select(TriageRun, Ticket.category, Ticket.labels)
            .join(Ticket, Ticket.id == TriageRun.ticket_id)
            .where(*_in_range(TriageRun, project_id, since, until))
        )
    ).all()
    runs = [run for run, _, _ in rows]
    accepted = [run for run in runs if run.status is TriageStatus.APPLIED]
    auto_applied = unchanged = 0
    for run, category, labels in rows:
        proposal = run.proposal or {}
        now = {"category": category.value if category else None, "labels": labels}
        for field in run.auto_applied:
            auto_applied += 1
            unchanged += _same(now[field], proposal.get(field))
    return TriageMetrics(
        runs=len(runs),
        accepted=len(accepted),
        dismissed=sum(run.status is TriageStatus.DISMISSED for run in runs),
        failed=sum(run.status is TriageStatus.FAILED for run in runs),
        waiting=sum(run.status in _WAITING for run in runs),
        fields=[_acceptance(field, accepted) for field in SUGGESTED_FIELDS],
        auto_applied=auto_applied,
        auto_applied_unchanged=unchanged,
        cost=await _cost(session, TriageRun, project_id, since, until),
    )


async def _assignment(
    session: AsyncSession, project_id: uuid.UUID, since: datetime, until: datetime
) -> AssignmentMetrics:
    conditions = _in_range(AssignmentRun, project_id, since, until)
    row = (
        await session.execute(
            select(
                func.count(),
                func.count(AssignmentRun.decided_at),
                func.count().filter(AssignmentRun.chosen_rank == 1),
                func.count().filter(AssignmentRun.chosen_rank.is_not(None)),
                _percentile(0.95, AssignmentRun.score_ms),
            )
            .select_from(AssignmentRun)
            .join(Ticket, Ticket.id == AssignmentRun.ticket_id)
            .where(*conditions)
        )
    ).one()
    runs, decided, top1, top3, score_p95 = row
    return AssignmentMetrics(
        runs=runs,
        decided=decided,
        top1_rate=round(top1 / decided, 3) if decided else None,
        top3_rate=round(top3 / decided, 3) if decided else None,
        score_p95_ms=_rounded(score_p95),
        cost=await _cost(session, AssignmentRun, project_id, since, until),
    )


async def _cost(
    session: AsyncSession, model: RunModel, project_id: uuid.UUID, since: datetime, until: datetime
) -> AgentCost:
    query = (
        select(
            func.count(),
            func.coalesce(func.sum(model.cost_usd), 0.0),
            _percentile(0.5, model.latency_ms),
            _percentile(0.95, model.latency_ms),
        )
        .select_from(model)
        .join(Ticket, Ticket.id == model.ticket_id)
        .where(*_in_range(model, project_id, since, until), model.llm_calls > 0)
    )
    row = (await session.execute(query)).one()
    runs, cost = int(row[0]), float(row[1])
    return AgentCost(
        runs=runs,
        cost_usd=round(cost, 6),
        cost_per_run_usd=round(cost / runs, 6) if runs else None,
        latency_p50_ms=_rounded(row[2]),
        latency_p95_ms=_rounded(row[3]),
    )


def _acceptance(field: str, accepted: list[TriageRun]) -> FieldAcceptance:
    kept = edited = left_out = 0
    for run in accepted:
        chosen = run.accepted or {}
        if field not in chosen:
            left_out += 1
        elif _same(chosen[field], (run.proposal or {}).get(field)):
            kept += 1
        else:
            edited += 1
    return FieldAcceptance(field=field, kept=kept, edited=edited, left_out=left_out)


def _same(a: object, b: object) -> bool:
    # Label order means nothing: ["db", "api"] is the same suggestion as ["api", "db"].
    if isinstance(a, list) and isinstance(b, list):
        return _sorted(typing.cast("list[object]", a)) == _sorted(typing.cast("list[object]", b))
    return a == b


def _sorted(values: list[object]) -> list[str]:
    return sorted(str(v) for v in values)


def _in_range(
    model: RunModel, project_id: uuid.UUID, since: datetime, until: datetime
) -> list[Any]:
    return [Ticket.project_id == project_id, model.created_at >= since, model.created_at < until]


def _percentile(fraction: float, column: Any) -> Any:
    return func.percentile_cont(fraction).within_group(cast(column, Float))


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(float(value), 1)
