import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.services.email import get_email_sender
from app.services.embeddings import Embedder, get_embedder
from tests.fakes import FakeEmbedder, Outbox

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB = "pm_test"


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
