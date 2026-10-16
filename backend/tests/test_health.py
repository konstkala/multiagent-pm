from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

from app.db.session import get_session
from app.main import app


class UnreachableSession:
    async def execute(self, *_: object) -> None:
        raise ConnectionRefusedError


async def unreachable_session() -> AsyncIterator[UnreachableSession]:
    yield UnreachableSession()


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_db_returns_503_when_db_unreachable(client: AsyncClient) -> None:
    app.dependency_overrides[get_session] = unreachable_session

    response = await client.get("/health/db")

    assert response.status_code == 503


@pytest.mark.db
async def test_health_db_returns_ok_when_db_up(client: AsyncClient) -> None:
    response = await client.get("/health/db")

    assert response.status_code == 200
