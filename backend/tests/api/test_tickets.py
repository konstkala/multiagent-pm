import json
import logging
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.db


async def create(
    client: AsyncClient, title: str = "Printer is on fire", **extra: object
) -> dict[str, Any]:
    response = await client.post("/tickets", json={"title": title, **extra})
    assert response.status_code == 201
    return response.json()


async def test_create_ticket_returns_defaults(db_client: AsyncClient) -> None:
    ticket = await create(db_client, description="Smoke from the tray")

    assert uuid.UUID(ticket["id"])
    assert ticket["status"] == "open"
    assert ticket["labels"] == []
    assert ticket["type"] is None
    assert ticket["priority"] is None
    assert ticket["created_at"] == ticket["updated_at"] or ticket["updated_at"]


async def test_create_ticket_rejects_empty_title_with_standard_error(
    db_client: AsyncClient,
) -> None:
    response = await db_client.post("/tickets", json={"title": ""})

    error = response.json()["error"]
    assert response.status_code == 422
    assert error["code"] == "validation_error"
    assert error["message"].startswith("title: ")


async def test_get_ticket_returns_the_ticket(db_client: AsyncClient) -> None:
    created = await create(db_client)

    response = await db_client.get(f"/tickets/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


async def test_get_unknown_ticket_returns_standard_404(db_client: AsyncClient) -> None:
    response = await db_client.get(f"/tickets/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_get_ticket_with_malformed_id_returns_422(db_client: AsyncClient) -> None:
    response = await db_client.get("/tickets/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_list_tickets_is_newest_first_and_paginated(db_client: AsyncClient) -> None:
    for number in range(3):
        await create(db_client, title=f"ticket {number}")

    first = (await db_client.get("/tickets", params={"limit": 2})).json()
    second = (await db_client.get("/tickets", params={"limit": 2, "offset": 2})).json()

    assert first["total"] == 3
    assert [t["title"] for t in first["items"]] == ["ticket 2", "ticket 1"]
    assert [t["title"] for t in second["items"]] == ["ticket 0"]


async def test_list_tickets_rejects_oversized_limit(db_client: AsyncClient) -> None:
    response = await db_client.get("/tickets", params={"limit": 1000})

    assert response.status_code == 422


async def test_update_ticket_sets_triage_fields(db_client: AsyncClient) -> None:
    created = await create(db_client)

    response = await db_client.patch(
        f"/tickets/{created['id']}",
        json={"type": "bug", "priority": "high", "labels": ["hardware"], "assignee": "sam"},
    )

    updated = response.json()
    assert response.status_code == 200
    assert (updated["type"], updated["priority"], updated["assignee"]) == ("bug", "high", "sam")
    assert updated["labels"] == ["hardware"]
    assert updated["title"] == created["title"]
    assert updated["updated_at"] >= created["updated_at"]


async def test_update_ticket_can_clear_optional_field(db_client: AsyncClient) -> None:
    created = await create(db_client)
    await db_client.patch(f"/tickets/{created['id']}", json={"assignee": "sam"})

    response = await db_client.patch(f"/tickets/{created['id']}", json={"assignee": None})

    assert response.json()["assignee"] is None


async def test_update_ticket_rejects_null_title(db_client: AsyncClient) -> None:
    created = await create(db_client)

    response = await db_client.patch(f"/tickets/{created['id']}", json={"title": None})

    assert response.status_code == 422


async def test_update_ticket_rejects_unknown_status(db_client: AsyncClient) -> None:
    created = await create(db_client)

    response = await db_client.patch(f"/tickets/{created['id']}", json={"status": "bogus"})

    assert response.status_code == 422


async def test_update_unknown_ticket_returns_404(db_client: AsyncClient) -> None:
    response = await db_client.patch(f"/tickets/{uuid.uuid4()}", json={"status": "closed"})

    assert response.status_code == 404


async def test_duplicate_of_points_to_an_existing_other_ticket(db_client: AsyncClient) -> None:
    original = await create(db_client, title="original")
    copy = await create(db_client, title="copy")

    ok = await db_client.patch(f"/tickets/{copy['id']}", json={"duplicate_of": original["id"]})
    itself = await db_client.patch(f"/tickets/{copy['id']}", json={"duplicate_of": copy["id"]})
    missing = await db_client.patch(
        f"/tickets/{copy['id']}", json={"duplicate_of": str(uuid.uuid4())}
    )

    assert ok.json()["duplicate_of"] == original["id"]
    assert itself.status_code == 422
    assert missing.status_code == 422


async def test_audit_logs_record_changes_without_ticket_text(
    db_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.services.tickets")
    created = await create(db_client, title="Secret customer name", description="private body")

    await db_client.patch(
        f"/tickets/{created['id']}", json={"title": "Another secret", "priority": "urgent"}
    )

    audit = [r.__dict__["fields"] for r in caplog.records if r.getMessage().startswith("audit.")]
    assert [r.getMessage() for r in caplog.records] == [
        "audit.ticket.created",
        "audit.ticket.updated",
    ]
    assert audit[1]["changed_fields"] == ["priority", "title"]
    assert audit[1]["before"] == {"priority": None}
    assert audit[1]["after"] == {"priority": "urgent"}
    logged = json.dumps(audit, default=str)
    assert "secret" not in logged.lower()
    assert "private body" not in logged


async def test_database_rejects_invalid_status(db_session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await db_session.execute(text("INSERT INTO tickets (title, status) VALUES ('x', 'bogus')"))
