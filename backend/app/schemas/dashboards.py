import uuid
from datetime import date

from pydantic import BaseModel

from app.db.models import TicketPriority, TicketStatus


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


class MyTicket(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    key: str  # PM-42
    title: str
    status: TicketStatus
    priority: TicketPriority | None
    story_points: int | None
    due_date: date | None


class WeekDone(BaseModel):
    week: date
    done: int


class MyDashboard(BaseModel):
    """Your own work across every project you are in."""

    start: date
    end: date
    open_by_status: list[StatusCount]
    open_points: int
    overdue: list[MyTicket]
    due_soon: list[MyTicket]  # the next 7 days
    weeks: list[WeekDone]  # your tickets moved to Done
    done: int


class CalendarTicket(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    key: str
    title: str
    status: TicketStatus
    due_date: date
    assignee_id: uuid.UUID | None
