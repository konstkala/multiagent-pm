import json
import logging
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import Login

pytestmark = pytest.mark.db


async def create(
    client: AsyncClient, project_id: str, title: str = "Printer is on fire", **extra: object
) -> dict[str, Any]:
    response = await client.post(f"/projects/{project_id}/tickets", json={"title": title, **extra})
    assert response.status_code == 201
    return response.json()


async def test_create_ticket_returns_defaults_and_reporter(
    manager: AsyncClient, project_id: str
) -> None:
    ticket = await create(manager, project_id, description="Smoke from the tray")
    me = (await manager.get("/auth/me")).json()

    assert uuid.UUID(ticket["id"])
    assert ticket["project_id"] == project_id
    assert ticket["number"] == 1
    assert ticket["reporter_id"] == me["id"]
    assert ticket["status"] == "todo"
    assert ticket["labels"] == []
    assert ticket["category"] is None
    assert ticket["assignee_id"] is None
    assert ticket["story_points"] is None


async def test_ticket_numbers_count_up_per_project(manager: AsyncClient, project_id: str) -> None:
    numbers = [(await create(manager, project_id, f"t{i}"))["number"] for i in range(3)]

    assert numbers == [1, 2, 3]


async def test_tickets_need_a_signed_in_user(client: AsyncClient, project_id: str) -> None:
    response = await client.get(f"/projects/{project_id}/tickets")

    assert response.status_code == 401


async def test_create_ticket_rejects_empty_title_with_standard_error(
    manager: AsyncClient, project_id: str
) -> None:
    response = await manager.post(f"/projects/{project_id}/tickets", json={"title": ""})

    error = response.json()["error"]
    assert response.status_code == 422
    assert error["code"] == "validation_error"
    assert error["message"].startswith("title: ")


async def test_get_ticket_returns_the_ticket(manager: AsyncClient, project_id: str) -> None:
    created = await create(manager, project_id)

    response = await manager.get(f"/tickets/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


async def test_get_unknown_ticket_returns_standard_404(manager: AsyncClient) -> None:
    response = await manager.get(f"/tickets/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_get_ticket_with_malformed_id_returns_422(manager: AsyncClient) -> None:
    response = await manager.get("/tickets/not-a-uuid")

    assert response.status_code == 422


async def test_list_tickets_is_newest_first_and_paginated(
    manager: AsyncClient, project_id: str
) -> None:
    for number in range(3):
        await create(manager, project_id, title=f"ticket {number}")
    url = f"/projects/{project_id}/tickets"

    first = (await manager.get(url, params={"limit": 2})).json()
    second = (await manager.get(url, params={"limit": 2, "offset": 2})).json()

    assert first["total"] == 3
    assert [t["title"] for t in first["items"]] == ["ticket 2", "ticket 1"]
    assert [t["title"] for t in second["items"]] == ["ticket 0"]


async def test_list_tickets_rejects_oversized_limit(manager: AsyncClient, project_id: str) -> None:
    response = await manager.get(f"/projects/{project_id}/tickets", params={"limit": 1000})

    assert response.status_code == 422


async def test_manager_sets_all_planning_fields(manager: AsyncClient, project_id: str) -> None:
    created = await create(manager, project_id)
    me = (await manager.get("/auth/me")).json()["id"]

    response = await manager.patch(
        f"/tickets/{created['id']}",
        json={
            "category": "bug",
            "priority": "high",
            "labels": [" Hardware ", "printer"],
            "story_points": 5,
            "due_date": "2026-11-30",
            "assignee_id": me,
        },
    )

    updated = response.json()
    assert response.status_code == 200
    assert (updated["category"], updated["priority"]) == ("bug", "high")
    assert updated["labels"] == ["hardware", "printer"]  # trimmed and lowercased
    assert (updated["story_points"], updated["due_date"]) == (5, "2026-11-30")
    assert updated["assignee_id"] == me
    assert updated["updated_at"] >= created["updated_at"]


async def test_story_points_must_be_fibonacci(manager: AsyncClient, project_id: str) -> None:
    created = await create(manager, project_id)

    response = await manager.patch(f"/tickets/{created['id']}", json={"story_points": 4})

    assert response.status_code == 422


async def test_update_ticket_can_clear_optional_field(
    manager: AsyncClient, project_id: str
) -> None:
    created = await create(manager, project_id)
    me = (await manager.get("/auth/me")).json()["id"]
    await manager.patch(f"/tickets/{created['id']}", json={"assignee_id": me})

    response = await manager.patch(f"/tickets/{created['id']}", json={"assignee_id": None})

    assert response.json()["assignee_id"] is None


async def test_update_ticket_rejects_null_title_and_unknown_status(
    manager: AsyncClient, project_id: str
) -> None:
    created = await create(manager, project_id)

    null_title = await manager.patch(f"/tickets/{created['id']}", json={"title": None})
    bad_status = await manager.patch(f"/tickets/{created['id']}", json={"status": "bogus"})

    assert null_title.status_code == bad_status.status_code == 422


async def test_update_unknown_ticket_returns_404(manager: AsyncClient) -> None:
    response = await manager.patch(f"/tickets/{uuid.uuid4()}", json={"status": "done"})

    assert response.status_code == 404


async def test_duplicate_of_must_be_another_ticket_in_the_same_project(
    manager: AsyncClient, project_id: str
) -> None:
    original = await create(manager, project_id, title="original")
    copy = await create(manager, project_id, title="copy")
    workspace = (await manager.get("/workspaces")).json()[0]
    other_project = await manager.post(
        f"/workspaces/{workspace['id']}/projects", json={"key": "WEB", "name": "Website"}
    )
    elsewhere = await create(manager, other_project.json()["id"], title="elsewhere")

    async def mark(target: str) -> int:
        response = await manager.patch(f"/tickets/{copy['id']}", json={"duplicate_of": target})
        return response.status_code

    assert await mark(original["id"]) == 200
    assert await mark(copy["id"]) == 422
    assert await mark(elsewhere["id"]) == 422
    assert await mark(str(uuid.uuid4())) == 422


async def test_audit_logs_record_actor_and_changes_without_ticket_text(
    manager: AsyncClient, project_id: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.services.tickets")
    me = (await manager.get("/auth/me")).json()
    created = await create(manager, project_id, title="Secret customer name", description="body")

    await manager.patch(
        f"/tickets/{created['id']}", json={"title": "Another secret", "priority": "urgent"}
    )

    records = [r for r in caplog.records if r.getMessage().startswith("audit.")]
    assert [r.getMessage() for r in records] == ["audit.ticket.created", "audit.ticket.updated"]
    updated = records[1].__dict__["fields"]
    assert str(updated["actor"]) == me["id"]
    assert updated["changed_fields"] == ["priority", "title"]
    assert updated["before"] == {"priority": None}
    assert updated["after"] == {"priority": "urgent"}
    assert "secret" not in json.dumps([r.__dict__["fields"] for r in records], default=str).lower()


async def test_database_rejects_invalid_status(db_session: AsyncSession, project_id: str) -> None:
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO tickets (project_id, number, title, status) "
                "VALUES (:project, 99, 'x', 'bogus')"
            ),
            {"project": project_id},
        )


async def test_outsiders_cannot_see_or_change_tickets(
    manager: AsyncClient, project_id: str, login: Login
) -> None:
    ticket = await create(manager, project_id)
    outsider = await login("outsider")

    listed = await outsider.get(f"/projects/{project_id}/tickets")
    read = await outsider.get(f"/tickets/{ticket['id']}")
    changed = await outsider.patch(f"/tickets/{ticket['id']}", json={"priority": "low"})
    created = await outsider.post(f"/projects/{project_id}/tickets", json={"title": "spam"})

    assert {listed.status_code, read.status_code, changed.status_code, created.status_code} == {404}
