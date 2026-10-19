import asyncio
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.api.deps import SESSION_COOKIE
from app.api.middleware import CSRF_HEADER
from app.core.config import settings
from app.core.security import hash_token, new_token
from app.db.models import User, UserSession
from app.db.session import get_session
from app.main import app
from app.services.email import get_email_sender
from app.services.embeddings import Embedder, get_embedder
from tests.fakes import FakeEmbedder, Outbox

# psycopg (LangGraph's checkpointer) can't run on Windows' default Proactor event loop.
if sys.platform == "win32":
    # Deprecated from Python 3.14, which this project does not use (requires-python is 3.12).
    asyncio.set_event_loop_policy(  # pyright: ignore[reportDeprecated]
        asyncio.WindowsSelectorEventLoopPolicy()  # pyright: ignore[reportDeprecated]
    )

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB = "pm_test"

Login = Callable[[str], Awaitable[AsyncClient]]


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine]:
    """A throwaway database built by the real migrations, so dev data is never touched."""
    base_url = make_url(settings.database_url)
    admin = create_async_engine(base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    await admin.dispose()

    test_url = base_url.set(database=TEST_DB).render_as_string(hide_password=False)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", test_url)
    # Alembic starts its own event loop, so it cannot run inside this one.
    await asyncio.to_thread(command.upgrade, config, "head")

    engine = create_async_engine(test_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Each test runs in an outer transaction that is rolled back; commits become savepoints."""
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        yield session
        await session.close()
        await transaction.rollback()


@pytest.fixture
def embedder() -> Embedder:
    return FakeEmbedder()


@pytest.fixture
def outbox() -> Outbox:
    return Outbox()


@pytest.fixture
async def db_client(
    client: AsyncClient, db_session: AsyncSession, embedder: Embedder, outbox: Outbox
) -> AsyncClient:
    async def use_test_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = use_test_session
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_email_sender] = lambda: outbox
    return client


@pytest.fixture
async def login(db_client: AsyncClient, db_session: AsyncSession) -> AsyncGenerator[Login]:
    """Creates a verified, signed-in user and returns their own browser-like client."""
    browsers: list[AsyncClient] = []

    async def sign_in_as(name: str) -> AsyncClient:
        now = datetime.now(UTC)
        user = User(email=f"{name}@example.com", display_name=name.title(), email_verified_at=now)
        db_session.add(user)
        await db_session.flush()
        token = new_token()
        db_session.add(
            UserSession(
                user_id=user.id, token_hash=hash_token(token), expires_at=now + timedelta(days=1)
            )
        )
        await db_session.flush()
        browser = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
            cookies={SESSION_COOKIE: token},
            headers={CSRF_HEADER: "fetch"},
        )
        browsers.append(browser)
        return browser

    yield sign_in_as
    for browser in browsers:
        await browser.aclose()


@pytest.fixture
async def manager(login: Login) -> AsyncClient:
    return await login("manager")


@pytest.fixture
async def project_id(manager: AsyncClient) -> str:
    """A workspace with one project, PM, managed by `manager`."""
    workspace = (await manager.post("/workspaces", json={"name": "Acme"})).json()
    project = await manager.post(
        f"/workspaces/{workspace['id']}/projects", json={"key": "PM", "name": "Platform"}
    )
    assert project.status_code == 201
    return project.json()["id"]


@pytest.fixture
async def employee(manager: AsyncClient, project_id: str, login: Login) -> AsyncClient:
    """`emp@example.com`, an employee in the `PM` project."""
    browser = await login("emp")
    added = await manager.post(
        f"/projects/{project_id}/members", json={"email": "emp@example.com", "role": "employee"}
    )
    assert added.status_code == 201
    return browser
