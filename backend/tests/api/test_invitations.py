import json
import logging
import re
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProjectInvitation
from tests.conftest import Login
from tests.fakes import Outbox

pytestmark = pytest.mark.db


def invite_token(outbox: Outbox) -> str:
    message = next(m for m in reversed(outbox.sent) if m.template == "project_invitation")
    match = re.search(r"token=([\w-]+)", message.body)
    assert match is not None
    return match.group(1)


async def invite(manager: AsyncClient, project_id: str, email: str, role: str = "employee") -> int:
    response = await manager.post(
        f"/projects/{project_id}/invitations", json={"email": email, "role": role}
    )
    return response.status_code


async def test_invited_person_accepts_and_joins_with_the_role(
    manager: AsyncClient, project_id: str, login: Login, outbox: Outbox
) -> None:
    assert await invite(manager, project_id, "New.Person@Example.com", "manager") == 201
    newcomer = await login("new.person")
    token = invite_token(outbox)

    preview = (await newcomer.post("/invitations/preview", json={"token": token})).json()
    accepted = await newcomer.post("/invitations/accept", json={"token": token})
    project = await newcomer.get(f"/projects/{project_id}")

    assert (preview["project_name"], preview["status"], preview["role"]) == (
        "Platform",
        "pending",
        "manager",
    )
    assert preview["email"] == "new.person@example.com"
    assert accepted.json() == {"project_id": project_id}
    assert project.json()["role"] == "manager"


async def test_preview_works_before_signing_in(
    manager: AsyncClient, project_id: str, client: AsyncClient, outbox: Outbox
) -> None:
    await invite(manager, project_id, "someone@example.com")

    response = await client.post("/invitations/preview", json={"token": invite_token(outbox)})

    assert response.status_code == 200
    assert response.json()["inviter_name"] == "Manager"


async def test_forwarded_link_cannot_be_used_by_another_account(
    manager: AsyncClient, project_id: str, login: Login, outbox: Outbox
) -> None:
    await invite(manager, project_id, "intended@example.com")
    intruder = await login("intruder")

    response = await intruder.post("/invitations/accept", json={"token": invite_token(outbox)})

    assert response.status_code == 403
    assert (await intruder.get(f"/projects/{project_id}")).status_code == 404


async def test_invitation_works_once(
    manager: AsyncClient, project_id: str, login: Login, outbox: Outbox
) -> None:
    await invite(manager, project_id, "once@example.com")
    person = await login("once")
    token = invite_token(outbox)

    first = await person.post("/invitations/accept", json={"token": token})
    second = await person.post("/invitations/accept", json={"token": token})

    assert first.status_code == 200
    assert second.status_code == 422


async def test_reinviting_replaces_the_old_link(
    manager: AsyncClient, project_id: str, login: Login, outbox: Outbox
) -> None:
    await invite(manager, project_id, "twice@example.com")
    old = invite_token(outbox)
    await invite(manager, project_id, "twice@example.com")
    person = await login("twice")

    with_old = await person.post("/invitations/accept", json={"token": old})
    pending = (await manager.get(f"/projects/{project_id}/invitations")).json()

    assert with_old.status_code == 422
    assert [i["email"] for i in pending] == ["twice@example.com"]


async def test_expired_and_revoked_invitations_are_refused(
    manager: AsyncClient,
    project_id: str,
    login: Login,
    outbox: Outbox,
    db_session: AsyncSession,
) -> None:
    await invite(manager, project_id, "late@example.com")
    late_token = invite_token(outbox)
    await db_session.execute(
        update(ProjectInvitation)
        .where(ProjectInvitation.email == "late@example.com")
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await invite(manager, project_id, "revoked@example.com")
    revoked_token = invite_token(outbox)
    pending = (await manager.get(f"/projects/{project_id}/invitations")).json()
    await manager.delete(f"/invitations/{pending[0]['id']}")
    late, revoked = await login("late"), await login("revoked")

    expired_preview = (await late.post("/invitations/preview", json={"token": late_token})).json()
    late_accept = await late.post("/invitations/accept", json={"token": late_token})
    revoked_accept = await revoked.post("/invitations/accept", json={"token": revoked_token})

    assert expired_preview["status"] == "expired"
    assert late_accept.status_code == revoked_accept.status_code == 422


async def test_only_managers_invite_and_members_are_not_reinvited(
    manager: AsyncClient, employee: AsyncClient, project_id: str
) -> None:
    by_employee = await invite(employee, project_id, "friend@example.com")
    existing_member = await invite(manager, project_id, "emp@example.com")

    assert by_employee == 403
    assert existing_member == 409


async def test_accepting_requires_signing_in(
    manager: AsyncClient, project_id: str, client: AsyncClient, outbox: Outbox
) -> None:
    await invite(manager, project_id, "anon@example.com")

    response = await client.post("/invitations/accept", json={"token": invite_token(outbox)})

    assert response.status_code == 401


async def test_invitation_logs_carry_no_email_or_token(
    manager: AsyncClient,
    project_id: str,
    login: Login,
    outbox: Outbox,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    await invite(manager, project_id, "private.person@example.com")
    person = await login("private.person")
    token = invite_token(outbox)
    await person.post("/invitations/accept", json={"token": token})

    logged = json.dumps([r.__dict__.get("fields", {}) for r in caplog.records], default=str)
    events = [r.getMessage() for r in caplog.records]
    assert "private.person@example.com" not in logged
    assert token not in logged
    assert "audit.invitation.created" in events
    assert "audit.invitation.accepted" in events
