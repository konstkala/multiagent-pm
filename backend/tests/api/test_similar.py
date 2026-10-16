import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.main import app
from app.services.embeddings import get_embedder
from tests.fakes import BrokenEmbedder

pytestmark = pytest.mark.db

LOGIN_BUG = "Login page returns 500 after password reset"
LOGIN_BUG_REWORDED = "Password reset then login page returns 500 error"
DARK_MODE = "Add dark mode toggle to the settings screen"


async def create(client: AsyncClient, project_id: str, title: str) -> dict[str, Any]:
    response = await client.post(f"/projects/{project_id}/tickets", json={"title": title})
    assert response.status_code == 201
    return response.json()


async def similar(client: AsyncClient, ticket_id: str, **params: float) -> list[dict[str, Any]]:
    response = await client.get(f"/tickets/{ticket_id}/similar", params=params)
    assert response.status_code == 200
    return response.json()["items"]


async def test_similar_ranks_related_ticket_first_and_excludes_self(
    manager: AsyncClient, project_id: str
) -> None:
    target = await create(manager, project_id, LOGIN_BUG)
    related = await create(manager, project_id, LOGIN_BUG_REWORDED)
    await create(manager, project_id, DARK_MODE)

    items = await similar(manager, target["id"], min_similarity=0.0)

    assert items[0]["ticket"]["id"] == related["id"]
    assert target["id"] not in [i["ticket"]["id"] for i in items]
    assert items[0]["similarity"] > items[1]["similarity"]


async def test_similar_min_similarity_filters_out_unrelated_tickets(
    manager: AsyncClient, project_id: str
) -> None:
    target = await create(manager, project_id, LOGIN_BUG)
    related = await create(manager, project_id, LOGIN_BUG_REWORDED)
    await create(manager, project_id, DARK_MODE)

    items = await similar(manager, target["id"], min_similarity=0.5)

    assert [i["ticket"]["id"] for i in items] == [related["id"]]


async def test_similar_never_returns_tickets_from_another_project(
    manager: AsyncClient, project_id: str
) -> None:
    target = await create(manager, project_id, LOGIN_BUG)
    workspace = (await manager.get("/workspaces")).json()[0]
    other = await manager.post(
        f"/workspaces/{workspace['id']}/projects", json={"key": "WEB", "name": "Website"}
    )
    await create(manager, other.json()["id"], LOGIN_BUG_REWORDED)

    assert await similar(manager, target["id"], min_similarity=0.0) == []


async def test_similar_respects_limit(manager: AsyncClient, project_id: str) -> None:
    target = await create(manager, project_id, LOGIN_BUG)
    for _ in range(3):
        await create(manager, project_id, LOGIN_BUG_REWORDED)

    items = await similar(manager, target["id"], limit=2, min_similarity=0.0)

    assert len(items) == 2


async def test_embedding_is_stored_but_not_exposed(manager: AsyncClient, project_id: str) -> None:
    ticket = await create(manager, project_id, LOGIN_BUG)

    assert "embedding" not in ticket
    assert "embedding_model" not in ticket


async def test_editing_title_re_embeds_the_ticket(manager: AsyncClient, project_id: str) -> None:
    login = await create(manager, project_id, LOGIN_BUG)
    other = await create(manager, project_id, DARK_MODE)
    before = await similar(manager, login["id"], min_similarity=0.5)

    await manager.patch(f"/tickets/{other['id']}", json={"title": LOGIN_BUG_REWORDED})
    after = await similar(manager, login["id"], min_similarity=0.5)

    assert before == []
    assert [i["ticket"]["id"] for i in after] == [other["id"]]


async def test_similar_for_unknown_ticket_returns_404(manager: AsyncClient) -> None:
    response = await manager.get(f"/tickets/{uuid.uuid4()}/similar")

    assert response.status_code == 404


async def test_ticket_is_saved_when_embedding_fails_and_similar_returns_409(
    manager: AsyncClient, project_id: str
) -> None:
    app.dependency_overrides[get_embedder] = lambda: BrokenEmbedder()

    created = await manager.post(f"/projects/{project_id}/tickets", json={"title": LOGIN_BUG})
    response = await manager.get(f"/tickets/{created.json()['id']}/similar")

    assert created.status_code == 201
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_stale_embedding_is_cleared_when_re_embedding_fails(
    manager: AsyncClient, project_id: str
) -> None:
    ticket = await create(manager, project_id, LOGIN_BUG)
    app.dependency_overrides[get_embedder] = lambda: BrokenEmbedder()

    await manager.patch(f"/tickets/{ticket['id']}", json={"title": DARK_MODE})
    response = await manager.get(f"/tickets/{ticket['id']}/similar")

    assert response.status_code == 409
