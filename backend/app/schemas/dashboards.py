import uuid
from datetime import date

from pydantic import BaseModel

from app.db.models import TicketStatus


class WeekCounts(BaseModel):
    week: date  # the Monday
    created: int
    done: int  # moves to Done that week (a reopened ticket can count twice)


class Duration(BaseModel):
    """Days, over the tickets finished in the range. None when there are none."""

    median_days: float | None
    p90_days: float | None
    tickets: int


class StatusCount(BaseModel):
    status: TicketStatus
    count: int


class OpenAge(BaseModel):
    up_to_7_days: int
    days_8_to_30: int
    over_30_days: int


class WorkloadRow(BaseModel):
    user_id: uuid.UUID
    display_name: str
    open_tickets: int
    open_points: int  # an unpointed ticket counts as 3
    overdue: int


class ProjectDashboard(BaseModel):
    start: date
    end: date
    exact_history_since: date  # earlier history was rebuilt from the tickets' state
    weeks: list[WeekCounts]
    created: int
    done: int
    cycle_time: Duration  # first In progress to Done
    lead_time: Duration  # created to Done
    open_by_status: list[StatusCount]
    overdue: int
    open_age: OpenAge
    # Everyone for managers; only your own row for employees.
    workload: list[WorkloadRow]
