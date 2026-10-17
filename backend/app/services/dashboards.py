"""KPIs computed on request with plain SQL over tickets and their events (ADR 0019).

Fine at our size; the production version precomputes daily rollups once queries get slow."""

import logging
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from datetime import time as day_start
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.assignment.scoring import UNPOINTED
from app.core.errors import InvalidRequestError
from app.core.logging import log_fields
from app.db.models import ProjectRole, TicketStatus, User
from app.schemas.dashboards import (
    Duration,
    OpenAge,
    ProjectDashboard,
    StatusCount,
    WeekCounts,
    WorkloadRow,
)
from app.services import access

logger = logging.getLogger(__name__)

DEFAULT_DAYS = 30
MAX_DAYS = 366
EXACT_HISTORY_SINCE = date(2026, 10, 17)  # migration 0016 rebuilt everything before this
_OPEN = ("todo", "in_progress", "in_review")
_SECONDS_PER_DAY = 86_400


def date_range(start: date | None, end: date | None) -> tuple[date, date]:
    """Inclusive days; the last 30 by default."""
    end = end or datetime.now(UTC).date()
    start = start or end - timedelta(days=DEFAULT_DAYS - 1)
    if start > end:
        raise InvalidRequestError("The start date must be on or before the end date")
    if (end - start).days + 1 > MAX_DAYS:
        raise InvalidRequestError(f"Choose a range of at most {MAX_DAYS} days")
    return start, end


async def project_dashboard(
    session: AsyncSession, project_id: uuid.UUID, actor: User, start: date, end: date
) -> ProjectDashboard:
    role = await access.project_role(session, project_id, actor)
    started = time.perf_counter()
    params: dict[str, Any] = {
        "project_id": project_id,
        "since": datetime.combine(start, day_start.min, UTC),
        "until": datetime.combine(end + timedelta(days=1), day_start.min, UTC),
        "today": datetime.now(UTC).date(),
    }
    weeks = await _weeks(session, params, start, end)
    cycle, lead = await _durations(session, params)
    dashboard = ProjectDashboard(
        start=start,
        end=end,
        exact_history_since=EXACT_HISTORY_SINCE,
        weeks=weeks,
        created=sum(w.created for w in weeks),
        done=sum(w.done for w in weeks),
        cycle_time=cycle,
        lead_time=lead,
        open_by_status=await _open_by_status(session, params),
        overdue=await _overdue(session, params),
        open_age=await _open_age(session, params),
        workload=await _workload(
            session, params, only=None if role is ProjectRole.MANAGER else actor.id
        ),
    )
    logger.info(
        "dashboard.computed",
        extra=log_fields(
            project_id=project_id,
            range_days=(end - start).days + 1,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        ),
    )
    return dashboard


async def _weeks(
    session: AsyncSession, params: dict[str, Any], start: date, end: date
) -> list[WeekCounts]:
    rows = await session.execute(
        text(
            "SELECT date_trunc('week', created_at AT TIME ZONE 'UTC')::date AS week, "
            "count(*) FILTER (WHERE kind = 'created') AS created, "
            "count(*) FILTER (WHERE kind = 'status' AND to_value = 'done') AS done "
            "FROM ticket_events WHERE project_id = :project_id "
            "AND created_at >= :since AND created_at < :until GROUP BY week"
        ),
        params,
    )
    counts = {row.week: (row.created, row.done) for row in rows}
    monday = start - timedelta(days=start.weekday())
    weeks: list[WeekCounts] = []
    while monday <= end:  # every week shows, including empty ones
        created, done = counts.get(monday, (0, 0))
        weeks.append(WeekCounts(week=monday, created=created, done=done))
        monday += timedelta(days=7)
    return weeks


async def _durations(session: AsyncSession, params: dict[str, Any]) -> tuple[Duration, Duration]:
    """For tickets finished in the range: from the first move to In progress (cycle) and from
    creation (lead) to their last move to Done."""
    row = (
        await session.execute(
            text(
                "WITH finished AS ("
                "  SELECT ticket_id, max(created_at) AS done_at FROM ticket_events"
                "  WHERE project_id = :project_id AND kind = 'status' AND to_value = 'done'"
                "  AND created_at >= :since AND created_at < :until GROUP BY ticket_id"
                "), started AS ("
                "  SELECT e.ticket_id, min(e.created_at) AS started_at FROM ticket_events e"
                "  JOIN finished f ON f.ticket_id = e.ticket_id"
                "  WHERE e.kind = 'status' AND e.to_value = 'in_progress'"
                "  AND e.created_at <= f.done_at GROUP BY e.ticket_id"
                "), spans AS ("
                "  SELECT extract(epoch FROM f.done_at - s.started_at) AS cycle,"
                "  extract(epoch FROM f.done_at - t.created_at) AS lead"
                "  FROM finished f JOIN tickets t ON t.id = f.ticket_id"
                "  LEFT JOIN started s ON s.ticket_id = f.ticket_id"
                ") SELECT"
                " percentile_cont(0.5) WITHIN GROUP (ORDER BY cycle) AS cycle_p50,"
                " percentile_cont(0.9) WITHIN GROUP (ORDER BY cycle) AS cycle_p90,"
                " count(cycle) AS cycle_n,"
                " percentile_cont(0.5) WITHIN GROUP (ORDER BY lead) AS lead_p50,"
                " percentile_cont(0.9) WITHIN GROUP (ORDER BY lead) AS lead_p90,"
                " count(lead) AS lead_n FROM spans"
            ),
            params,
        )
    ).one()
    return _duration(row.cycle_p50, row.cycle_p90, row.cycle_n), _duration(
        row.lead_p50, row.lead_p90, row.lead_n
    )


async def _open_by_status(session: AsyncSession, params: dict[str, Any]) -> list[StatusCount]:
    rows = await session.execute(
        text(
            "SELECT status, count(*) AS n FROM tickets WHERE project_id = :project_id "
            "AND status = ANY(:open) GROUP BY status"
        ),
        params | {"open": list(_OPEN)},
    )
    counts = {row.status: row.n for row in rows}
    return [StatusCount(status=TicketStatus(s), count=counts.get(s, 0)) for s in _OPEN]


async def _overdue(session: AsyncSession, params: dict[str, Any]) -> int:
    return (
        await session.scalar(
            text(
                "SELECT count(*) FROM tickets WHERE project_id = :project_id "
                "AND status = ANY(:open) AND due_date < :today"
            ),
            params | {"open": list(_OPEN)},
        )
        or 0
    )


async def _open_age(session: AsyncSession, params: dict[str, Any]) -> OpenAge:
    row = (
        await session.execute(
            text(
                "SELECT count(*) FILTER (WHERE age <= 7) AS young,"
                " count(*) FILTER (WHERE age > 7 AND age <= 30) AS middle,"
                " count(*) FILTER (WHERE age > 30) AS old FROM ("
                "  SELECT :today - (created_at AT TIME ZONE 'UTC')::date AS age FROM tickets"
                "  WHERE project_id = :project_id AND status = ANY(:open)"
                ") AS open_tickets"
            ),
            params | {"open": list(_OPEN)},
        )
    ).one()
    return OpenAge(up_to_7_days=row.young, days_8_to_30=row.middle, over_30_days=row.old)


async def _workload(
    session: AsyncSession, params: dict[str, Any], only: uuid.UUID | None
) -> list[WorkloadRow]:
    rows = await session.execute(
        text(
            "SELECT u.id, u.display_name, count(t.id) AS open_tickets,"
            # FILTER: with no open tickets the LEFT JOIN gives one empty row, which must count 0.
            " coalesce(sum(coalesce(t.story_points, :unpointed))"
            " FILTER (WHERE t.id IS NOT NULL), 0) AS open_points,"
            " count(t.id) FILTER (WHERE t.due_date < :today) AS overdue"
            " FROM project_members m JOIN users u ON u.id = m.user_id"
            " LEFT JOIN tickets t ON t.assignee_id = u.id AND t.project_id = m.project_id"
            "  AND t.status = ANY(:open)"
            " WHERE m.project_id = :project_id AND (CAST(:only AS uuid) IS NULL OR u.id = :only)"
            " GROUP BY u.id, u.display_name ORDER BY open_points DESC, u.display_name"
        ),
        params | {"open": list(_OPEN), "unpointed": UNPOINTED, "only": only},
    )
    return [
        WorkloadRow(
            user_id=row.id,
            display_name=row.display_name,
            open_tickets=row.open_tickets,
            open_points=row.open_points,
            overdue=row.overdue,
        )
        for row in rows
    ]


def _duration(p50: float | None, p90: float | None, tickets: int) -> Duration:
    return Duration(median_days=_days(p50), p90_days=_days(p90), tickets=tickets)


def _days(seconds: float | None) -> float | None:
    return None if seconds is None else round(float(seconds) / _SECONDS_PER_DAY, 1)
