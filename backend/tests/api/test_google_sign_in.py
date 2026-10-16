from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import OAUTH_STATE_COOKIE
from app.api.deps import SESSION_COOKIE
from app.core.security import hash_password
from app.db.models import OAuthIdentity, User
from app.main import app
from app.services.google import GoogleIdentity, get_google_client
from tests.fakes import FakeGoogle

pytestmark = pytest.mark.db


@pytest.fixture
def google(db_client: AsyncClient) -> FakeGoogle:
    fake = FakeGoogle()
    app.dependency_overrides[get_google_client] = lambda: fake
    return fake


async def start(client: AsyncClient) -> str:
    response = await client.get("/auth/google/start")
    assert response.status_code == 302
    return response.headers["location"]


async def callback(client: AsyncClient, google: FakeGoogle, state: str | None = None) -> str:
    response = await client.get(
        "/auth/google/callback", params={"code": "code-1", "state": state or google.last_state}
    )
    assert response.status_code == 302
    return response.headers["location"]


async def test_providers_reports_google_off_until_configured(db_client: AsyncClient) -> None:
    app.dependency_overrides[get_google_client] = lambda: None

    response = await db_client.get("/auth/providers")
    start_response = await db_client.get("/auth/google/start")

    assert response.json() == {"google": False}
    assert start_response.status_code == 404


async def test_new_google_user_is_created_verified_and_signed_in(
    db_client: AsyncClient, google: FakeGoogle
) -> None:
    location = await start(db_client)

    redirected = await callback(db_client, google)
    me = await db_client.get("/auth/me")

    assert location.startswith("https://accounts.example/auth?state=")
    assert redirected.endswith("/projects")
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"
    assert me.json()["display_name"] == "Ada L"
    assert me.json()["email_verified_at"] is not None


async def test_start_sets_a_browser_bound_state_cookie(
    db_client: AsyncClient, google: FakeGoogle
) -> None:
    response = await db_client.get("/auth/google/start")

    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith(f"{OAUTH_STATE_COOKIE}=")
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


async def test_callback_from_another_browser_is_rejected(
    db_client: AsyncClient, google: FakeGoogle
) -> None:
    await start(db_client)
    db_client.cookies.delete(OAUTH_STATE_COOKIE)  # e.g. an attacker's link opened by a victim

    redirected = await callback(db_client, google)

    assert redirected.endswith("/sign-in?error=google")
    assert SESSION_COOKIE not in db_client.cookies


async def test_state_works_only_once(db_client: AsyncClient, google: FakeGoogle) -> None:
    await start(db_client)
    state = google.last_state
    first = await callback(db_client, google, state)
    await db_client.post("/auth/sign-out", headers={"x-requested-with": "fetch"})
    db_client.cookies.set(OAUTH_STATE_COOKIE, state or "")

    second = await callback(db_client, google, state)

    assert first.endswith("/projects")
    assert second.endswith("/sign-in?error=google")


async def test_google_failure_redirects_without_signing_in(
    db_client: AsyncClient, google: FakeGoogle
) -> None:
    google.fail = True
    await start(db_client)

    redirected = await callback(db_client, google)

    assert redirected.endswith("/sign-in?error=google")
    assert (await db_client.get("/auth/me")).status_code == 401


async def test_unverified_google_email_is_refused(
    db_client: AsyncClient, google: FakeGoogle
) -> None:
    google.identity = GoogleIdentity("sub-x", "ada@example.com", email_verified=False, name=None)
    await start(db_client)

    assert (await callback(db_client, google)).endswith("/sign-in?error=google")


async def test_existing_verified_account_is_linked_and_keeps_its_password(
    db_client: AsyncClient, db_session: AsyncSession, google: FakeGoogle
) -> None:
    user = User(
        email="ada@example.com",
        display_name="Ada",
        password_hash=await hash_password("correct horse battery"),
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.flush()
    await start(db_client)

    await callback(db_client, google)
    me = (await db_client.get("/auth/me")).json()

    assert me["id"] == str(user.id)
    assert user.password_hash is not None
    linked = await db_session.scalar(select(OAuthIdentity).where(OAuthIdentity.user_id == user.id))
    assert linked is not None


async def test_unverified_account_loses_its_unproven_password_when_google_proves_the_email(
    db_client: AsyncClient, db_session: AsyncSession, google: FakeGoogle
) -> None:
    squatter = User(
        email="ada@example.com",
        display_name="Not Ada",
        password_hash=await hash_password("attacker password"),
    )
    db_session.add(squatter)
    await db_session.flush()
    await start(db_client)

    await callback(db_client, google)
    await db_session.refresh(squatter)

    assert squatter.password_hash is None
    assert squatter.email_verified_at is not None


async def test_returning_user_is_found_by_google_id_even_if_email_changed(
    db_client: AsyncClient, google: FakeGoogle
) -> None:
    await start(db_client)
    await callback(db_client, google)
    first_id = (await db_client.get("/auth/me")).json()["id"]
    await db_client.post("/auth/sign-out", headers={"x-requested-with": "fetch"})
    google.identity = GoogleIdentity(
        "google-sub-1", "ada.new@example.com", email_verified=True, name="Ada"
    )

    await start(db_client)
    await callback(db_client, google)

    assert (await db_client.get("/auth/me")).json()["id"] == first_id
