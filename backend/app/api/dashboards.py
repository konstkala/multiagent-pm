import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ErrorResponse
from app.schemas.agent_metrics import AgentMetrics
from app.schemas.dashboards import CalendarTicket, MyDashboard, ProjectDashboard
from app.services import agent_metrics, dashboards

router = APIRouter(tags=["dashboards"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (403, 404, 422)
}


@router.get("/projects/{project_id}/dashboard", responses=_ERRORS)
async def project_dashboard(
    project_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    start: date | None = None,
    end: date | None = None,
) -> ProjectDashboard:
    """Team KPIs for the inclusive date range (default: the last 30 days)."""
    start, end = dashboards.date_range(start, end)
    return await dashboards.project_dashboard(session, project_id, user, start, end)


@router.get("/projects/{project_id}/agent-metrics", responses=_ERRORS)
async def project_agent_metrics(
    project_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    start: date | None = None,
    end: date | None = None,
) -> AgentMetrics:
    """How the triage and assignment agents did: what managers kept, hit rate, $ and latency.
    Managers only."""
    start, end = dashboards.date_range(start, end)
    return await agent_metrics.agent_metrics(session, project_id, user, start, end)


@router.get("/me/dashboard", responses=_ERRORS)
async def my_dashboard(
    session: SessionDep, user: CurrentUser, start: date | None = None, end: date | None = None
) -> MyDashboard:
    """Your own work across your projects (default range: the last 30 days)."""
    start, end = dashboards.date_range(start, end)
    return await dashboards.my_dashboard(session, user, start, end)


@router.get("/calendar", responses=_ERRORS)
async def calendar(
    session: SessionDep, user: CurrentUser, start: date, end: date, mine: bool = False
) -> list[CalendarTicket]:
    """Tickets due between start and end (at most 62 days and 500 tickets) in your projects."""
    start, end = dashboards.date_range(start, end, max_days=dashboards.CALENDAR_MAX_DAYS)
    return await dashboards.calendar(session, user, start, end, mine=mine)
