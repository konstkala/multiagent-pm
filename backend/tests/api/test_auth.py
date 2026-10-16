import json
import logging
import re
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SESSION_COOKIE
from app.db.models import EmailToken
from tests.fakes import Outbox

pytestmark = pytest.mark.db

EMAIL = "Ada@Example.com"
PASSWORD = "correct horse battery"
NEW_PASSWORD = "brand new password"
CSRF = {"x-requested-with": "fetch"}


def token_from(outbox: Outbox, template: str) -> str:
    message = next(m for m in reversed(outbox.sent) if m.template == template)
    match = re.search(r"token=([\w-]+)", message.body)
    assert match is not None
    return match.group(1)


async def sign_up(client: AsyncClient, email: str = EMAIL, password: str = PASSWORD) -> None:
    response = await client.post(
        "/auth/sign-up", json={"email": email, "password": password, "display_name": "Ada"}
    )
    assert response.status_code == 202


async def verified_user(client: AsyncClient, outbox: Outbox) -> None:
    await sign_up(client)
    response = await client.post(
        "/auth/verify-email", json={"token": token_from(outbox, "verify_email")}
    )
    assert response.status_code == 200


async def sign_in(client: AsyncClient, password: str = PASSWORD) -> int:
    response = await client.post(
        "/auth/sign-in", json={"email": EMAIL, "password": password}, headers=CSRF
    )
    return response.status_code


async def test_full_flow_sign_up_verify_sign_in_me_sign_out(
    db_client: AsyncClient, outbox: Outbox
) -> None:
    await verified_user(db_client, outbox)

    signed_in = await sign_in(db_client)
    me = await db_client.get("/auth/me")
    signed_out = await db_client.post("/auth/sign-out", headers=CSRF)
    after = await db_client.get("/auth/me")

    assert signed_in == 200
    assert me.json()["email"] == "ada@example.com"  # normalised
    assert signed_out.status_code == 204
    assert after.status_code == 401


async def test_session_cookie_is_httponly_secure_lax(
    db_client: AsyncClient, outbox: Outbox
) -> None:
    await verified_user(db_client, outbox)

    response = await db_client.post("/auth/sign-in", json={"email": EMAIL, "password": PASSWORD})

    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie


async def test_sign_in_before_verifying_is_refused_with_its_own_code(
    db_client: AsyncClient,
) -> None:
    await sign_up(db_client)

    response = await db_client.post("/auth/sign-in", json={"email": EMAIL, "password": PASSWORD})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_not_verified"


async def test_wrong_password_and_unknown_email_look_identical(
    db_client: AsyncClient, outbox: Outbox
) -> None:
    await verified_user(db_client, outbox)

    wrong = await db_client.post("/auth/sign-in", json={"email": EMAIL, "password": "nope-nope-1"})
    unknown = await db_client.post(
        "/auth/sign-in", json={"email": "nobody@example.com", "password": PASSWORD}
    )

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_sign_up_with_existing_email_reveals_nothing(
    db_client: AsyncClient, outbox: Outbox
) -> None:
    await sign_up(db_client)

    response = await db_client.post(
        "/auth/sign-up",
        json={"email": EMAIL.upper(), "password": "another password", "display_name": "X"},
    )

    assert response.status_code == 202
    assert [m.template for m in outbox.sent] == ["verify_email", "account_exists"]


async def test_short_password_is_rejected_with_a_reason(db_client: AsyncClient) -> None:
    response = await db_client.post(
        "/auth/sign-up", json={"email": EMAIL, "password": "short", "display_name": "Ada"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"].startswith("password: ")


async def test_verification_link_works_once(db_client: AsyncClient, outbox: Outbox) -> None:
    await sign_up(db_client)
    token = token_from(outbox, "verify_email")

    first = await db_client.post("/auth/verify-email", json={"token": token})
    second = await db_client.post("/auth/verify-email", json={"token": token})

    assert first.status_code == 200
    assert second.status_code == 422


async def test_password_reset_changes_password_and_signs_out_everywhere(
    db_client: AsyncClient, outbox: Outbox
) -> None:
    await verified_user(db_client, outbox)
    await sign_in(db_client)

    await db_client.post("/auth/forgot-password", json={"email": EMAIL}, headers=CSRF)
    reset = await db_client.post(
        "/auth/reset-password",
        json={"token": token_from(outbox, "reset_password"), "password": NEW_PASSWORD},
        headers=CSRF,
    )

    assert reset.status_code == 200
    assert (await db_client.get("/auth/me")).status_code == 401
    assert await sign_in(db_client, PASSWORD) == 401
    assert await sign_in(db_client, NEW_PASSWORD) == 200


async def test_forgot_password_for_unknown_email_sends_nothing(
    db_client: AsyncClient, outbox: Outbox
) -> None:
    response = await db_client.post("/auth/forgot-password", json={"email": "ghost@example.com"})

    assert response.status_code == 202
    assert outbox.sent == []


async def test_only_the_newest_reset_link_works(db_client: AsyncClient, outbox: Outbox) -> None:
    await verified_user(db_client, outbox)
    await db_client.post("/auth/forgot-password", json={"email": EMAIL})
    old = token_from(outbox, "reset_password")
    await db_client.post("/auth/forgot-password", json={"email": EMAIL})

    response = await db_client.post(
        "/auth/reset-password", json={"token": old, "password": NEW_PASSWORD}
    )

    assert response.status_code == 422


async def test_expired_reset_link_is_rejected(
    db_client: AsyncClient, db_session: AsyncSession, outbox: Outbox
) -> None:
    await verified_user(db_client, outbox)
    await db_client.post("/auth/forgot-password", json={"email": EMAIL})
    await db_session.execute(
        update(EmailToken).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )

    response = await db_client.post(
        "/auth/reset-password",
        json={"token": token_from(outbox, "reset_password"), "password": NEW_PASSWORD},
    )

    assert response.status_code == 422


async def test_state_change_with_session_cookie_needs_csrf_header(
    db_client: AsyncClient, outbox: Outbox
) -> None:
    await verified_user(db_client, outbox)
    await sign_in(db_client)

    without = await db_client.post("/auth/sign-out")
    with_header = await db_client.post("/auth/sign-out", headers=CSRF)

    assert without.status_code == 403
    assert without.json()["error"]["code"] == "csrf_header_missing"
    assert with_header.status_code == 204


async def test_sign_in_is_rate_limited_per_email(db_client: AsyncClient, outbox: Outbox) -> None:
    await verified_user(db_client, outbox)
    for _ in range(10):
        assert await sign_in(db_client, "wrong password!") == 401

    assert await sign_in(db_client) == 429  # even the right password, until the window passes


async def test_auth_logs_never_contain_email_password_or_token(
    db_client: AsyncClient, outbox: Outbox, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    await verified_user(db_client, outbox)
    await sign_in(db_client)
    await sign_in(db_client, "wrong password!")
    await db_client.post("/auth/forgot-password", json={"email": EMAIL}, headers=CSRF)

    events = [r.getMessage() for r in caplog.records]
    logged = json.dumps([r.__dict__.get("fields", {}) for r in caplog.records], default=str)
    assert "ada@example.com" not in logged.lower()
    assert PASSWORD not in logged
    assert token_from(outbox, "reset_password") not in logged
    assert "audit.auth.signed_in" in events
    assert "audit.auth.sign_in_failed" in events
