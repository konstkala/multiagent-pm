import json
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ticket, TicketEvent, TicketEventKind, TicketStatus

pytestmark = pytest.mark.db

NOW = datetime.now(UTC)
TODAY = NOW.date()


async def create(manager: AsyncClient, project_id: str, **fields: Any) -> str:
    created = await manager.post(f"/projects/{project_id}/tickets", json={"title": "Task"} | fields)
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def events(session: AsyncSession, ticket_id: str) -> list[tuple[str, str | None, str | None]]:
    rows = await session.scalars(
        select(TicketEvent)
        .where(TicketEvent.ticket_id == uuid.UUID(ticket_id))
        .order_by(TicketEvent.created_at)
    )
    return [(e.kind.value, e.from_value, e.to_value) for e in rows]


async def history(
    session: AsyncSession, ticket_id: str, created_days_ago: float, *moves: tuple[str, float]
) -> None:
    """Rewrites a ticket's past: created N days ago, then each (status, days ago) move."""
    ticket = await session.get(Ticket, uuid.UUID(ticket_id))
    assert ticket is not None
    await session.execute(delete(TicketEvent).where(TicketEvent.ticket_id == ticket.id))
    ticket.created_at = NOW - timedelta(days=created_days_ago)
    session.add(
        TicketEvent(
            ticket_id=ticket.id,
            project_id=ticket.project_id,
            kind=TicketEventKind.CREATED,
            created_at=ticket.created_at,
        )
    )
    previous = TicketStatus.TODO
    for status, days_ago in moves:
        session.add(
            TicketEvent(
                ticket_id=ticket.id,
                project_id=ticket.project_id,
                kind=TicketEventKind.STATUS,
                from_value=previous.value,
                to_value=status,
                created_at=NOW - timedelta(days=days_ago),
            )
        )
        previous = TicketStatus(status)
    ticket.status = previous
    await session.commit()


# --- events ----------------------------------------------------------------------------------


async def test_ticket_changes_are_recorded_as_events(
    manager: AsyncClient, employee: AsyncClient, project_id: str, db_session: AsyncSession
) -> None:
    emp = (await employee.get("/auth/me")).json()["id"]
    ticket = await create(manager, project_id, assignee_id=emp)

    await employee.patch(f"/tickets/{ticket}", json={"status": "in_progress"})
    await manager.patch(f"/tickets/{ticket}", json={"status": "in_progress", "title": "Renamed"})
    await employee.post(f"/tickets/{ticket}/return", json={"reason": "Blocked by the API"})
    copy = (await manager.post(f"/tickets/{ticket}/copy")).json()["id"]

    assert await events(db_session, ticket) == [
        ("created", None, None),
        ("assignee", None, emp),
        ("status", "todo", "in_progress"),
        # The manager's second PATCH changed nothing tracked: no event.
        ("status", "in_progress", "todo"),
        ("assignee", emp, None),
    ]
    assert (await events(db_session, copy))[0] == ("created", None, None)


# --- the project dashboard -------------------------------------------------------------------


async def test_dashboard_counts_flow_and_times(
    manager: AsyncClient, project_id: str, db_session: AsyncSession
) -> None:
    quick = await create(manager, project_id)
    slow = await create(manager, project_id)
    stale = await create(manager, project_id, due_date=(TODAY - timedelta(days=1)).isoformat())
    fresh = await create(manager, project_id)
    await history(db_session, quick, 10, ("in_progress", 8), ("done", 6))  # cycle 2, lead 4
    await history(db_session, slow, 20, ("in_progress", 10), ("done", 2))  # cycle 8, lead 18
    await history(db_session, stale, 40)
    await history(db_session, fresh, 3, ("in_progress", 1))

    board = (await manager.get(f"/projects/{project_id}/dashboard")).json()
    last_five = (
        await manager.get(
            f"/projects/{project_id}/dashboard",
            params={"start": (TODAY - timedelta(days=4)).isoformat(), "end": TODAY.isoformat()},
        )
    ).json()

    assert (board["created"], board["done"]) == (3, 2)  # `stale` was created before the range
    assert board["cycle_time"] == {"median_days": 5.0, "p90_days": 7.4, "tickets": 2}
    assert board["lead_time"] == {"median_days": 11.0, "p90_days": 16.6, "tickets": 2}
    assert {s["status"]: s["count"] for s in board["open_by_status"]} == {
        "todo": 1,
        "in_progress": 1,
        "in_review": 0,
    }
    assert board["overdue"] == 1
    assert board["open_age"] == {"up_to_7_days": 1, "days_8_to_30": 0, "over_30_days": 1}
    assert sum(w["done"] for w in board["weeks"]) == 2
    assert all(date.fromisoformat(w["week"]).weekday() == 0 for w in board["weeks"])
    assert last_five["done"] == 1 and last_five["cycle_time"]["tickets"] == 1


async def test_workload_shows_everyone_to_managers_and_yourself_to_employees(
    manager: AsyncClient, employee: AsyncClient, project_id: str, login: Any
) -> None:
    emp = (await employee.get("/auth/me")).json()["id"]
    await create(manager, project_id, assignee_id=emp, story_points=5)
    await create(manager, project_id, assignee_id=emp)  # unpointed counts as 3
    outsider = await login("outsider")

    managed = (await manager.get(f"/projects/{project_id}/dashboard")).json()["workload"]
    own = (await employee.get(f"/projects/{project_id}/dashboard")).json()["workload"]

    assert [(r["display_name"], r["open_points"]) for r in managed] == [("Emp", 8), ("Manager", 0)]
    assert [(r["display_name"], r["open_tickets"]) for r in own] == [("Emp", 2)]
    assert (await outsider.get(f"/projects/{project_id}/dashboard")).status_code == 404


async def test_dashboard_rejects_bad_ranges(manager: AsyncClient, project_id: str) -> None:
    url = f"/projects/{project_id}/dashboard"

    backwards = await manager.get(url, params={"start": "2026-10-10", "end": "2026-10-01"})
    too_long = await manager.get(url, params={"start": "2024-01-01", "end": "2026-01-01"})

    assert backwards.status_code == too_long.status_code == 422


async def test_dashboard_logs_timing_not_content(
    manager: AsyncClient, project_id: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    await create(manager, project_id, title="Secret launch plan")

    await manager.get(f"/projects/{project_id}/dashboard")

    [record] = [r for r in caplog.records if r.getMessage() == "dashboard.computed"]
    fields = record.__dict__["fields"]
    assert fields["range_days"] == 30 and fields["duration_ms"] >= 0
    logged = json.dumps([r.__dict__.get("fields", {}) for r in caplog.records], default=str)
    assert "Secret" not in logged


# --- my work and the calendar ----------------------------------------------------------------


async def test_my_dashboard_lists_only_my_open_work(
    manager: AsyncClient, employee: AsyncClient, project_id: str, db_session: AsyncSession
) -> None:
    emp = (await employee.get("/auth/me")).json()["id"]
    late = await create(
        manager, project_id, assignee_id=emp, due_date=(TODAY - timedelta(days=2)).isoformat()
    )
    soon = await create(
        manager,
        project_id,
        assignee_id=emp,
        story_points=5,
        due_date=(TODAY + timedelta(days=3)).isoformat(),
    )
    finished = await create(manager, project_id, assignee_id=emp)
    await create(manager, project_id)  # nobody's
    await manager.patch(f"/tickets/{finished}", json={"status": "done"})

    mine = (await employee.get("/me/dashboard")).json()

    assert [t["id"] for t in mine["overdue"]] == [late]
    assert [t["id"] for t in mine["due_soon"]] == [soon]
    assert mine["overdue"][0]["key"] == "PM-1"
    assert mine["open_points"] == 3 + 5
    assert {s["status"]: s["count"] for s in mine["open_by_status"]}["todo"] == 2
    assert mine["done"] == 1


async def test_calendar_shows_due_tickets_from_my_projects_only(
    manager: AsyncClient, employee: AsyncClient, project_id: str, login: Any
) -> None:
    emp = (await employee.get("/auth/me")).json()["id"]
    in_range = (TODAY + timedelta(days=5)).isoformat()
    mine = await create(manager, project_id, assignee_id=emp, due_date=in_range)
    theirs = await create(manager, project_id, due_date=in_range)
    await create(manager, project_id, due_date=(TODAY + timedelta(days=90)).isoformat())
    stranger = await login("stranger")
    month = {"start": TODAY.isoformat(), "end": (TODAY + timedelta(days=30)).isoformat()}

    everything = (await employee.get("/calendar", params=month)).json()
    only_mine = (await employee.get("/calendar", params=month | {"mine": True})).json()
    too_long = await employee.get(
        "/calendar",
        params={"start": TODAY.isoformat(), "end": (TODAY + timedelta(days=90)).isoformat()},
    )

    assert {t["id"] for t in everything} == {mine, theirs}
    assert [t["id"] for t in only_mine] == [mine]
    assert (await stranger.get("/calendar", params=month)).json() == []
    assert too_long.status_code == 422
