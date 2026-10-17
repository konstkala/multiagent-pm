import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ErrorResponse
from app.schemas.dashboards import ProjectDashboard
from app.services import dashboards

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
