from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import assignment
from tests.api.test_assignment import reasons
from tests.api.test_triage import proposal, run_triage
from tests.conftest import Login
from tests.fakes import FakeClaude

pytestmark = pytest.mark.db


async def create(manager: AsyncClient, project_id: str, **fields: Any) -> str:
    body = {"title": "Login page returns 500"} | fields
    created = await manager.post(f"/projects/{project_id}/tickets", json=body)
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def metrics(client: AsyncClient, project_id: str) -> Any:
    return await client.get(f"/projects/{project_id}/agent-metrics")


async def test_triage_metrics_show_what_managers_kept_edited_or_left_out(
    manager: AsyncClient, project_id: str, db_session: AsyncSession
) -> None:
    accepted = await create(manager, project_id, category="bug")  # no auto-apply of category
    dismissed = await create(manager, project_id)
    for ticket in (accepted, dismissed):
        await run_triage(db_session, manager, ticket, FakeClaude(proposal()))
    run = (await manager.get(f"/tickets/{accepted}/triage")).json()
    # Proposal: bug, [auth, backend], high, 5. Keep category and points, edit priority, drop labels.
    await manager.post(
        f"/triage-runs/{run['id']}/accept",
        json={"category": "bug", "priority": "urgent", "story_points": 5},
    )
    other = (await manager.get(f"/tickets/{dismissed}/triage")).json()
    await manager.post(f"/triage-runs/{other['id']}/dismiss")
    await manager.patch(f"/tickets/{dismissed}", json={"category": "task"})  # undo the agent

    triage = (await metrics(manager, project_id)).json()["triage"]

    assert (triage["runs"], triage["accepted"], triage["dismissed"]) == (2, 1, 1)
    assert {f["field"]: (f["kept"], f["edited"], f["left_out"]) for f in triage["fields"]} == {
        "category": (1, 0, 0),
        "labels": (0, 0, 1),
        "priority": (0, 1, 0),
        "story_points": (1, 0, 0),
    }
    # Auto-applied: labels on `accepted`; category and labels on `dismissed`, category undone.
    assert (triage["auto_applied"], triage["auto_applied_unchanged"]) == (3, 2)
    assert triage["cost"]["runs"] == 2 and triage["cost"]["cost_usd"] > 0
    assert triage["cost"]["latency_p95_ms"] is not None


async def test_assignment_hit_rate_counts_decided_runs_only(
    manager: AsyncClient, employee: AsyncClient, project_id: str, db_session: AsyncSession
) -> None:
    emp = (await employee.get("/auth/me")).json()["id"]
    picked_first, picked_other, undecided = [await create(manager, project_id) for _ in range(3)]
    for ticket in (picked_first, picked_other, undecided):
        run = (await manager.post(f"/tickets/{ticket}/assignment-suggestions")).json()
        await assignment.run(db_session, {"run_id": run["id"]}, llm=FakeClaude(reasons("A")).client)
        if ticket == picked_first:
            await manager.patch(
                f"/tickets/{ticket}", json={"assignee_id": run["candidates"][0]["user_id"]}
            )
        elif ticket == picked_other:
            second = run["candidates"][1]["user_id"]
            assert second == emp
            await manager.patch(f"/tickets/{ticket}", json={"assignee_id": second})

    result = (await metrics(manager, project_id)).json()["assignment"]

    assert (result["runs"], result["decided"]) == (3, 2)
    assert (result["top1_rate"], result["top3_rate"]) == (0.5, 1.0)
    assert result["cost"]["runs"] == 3 and result["score_p95_ms"] is not None


async def test_only_managers_see_agent_metrics(
    manager: AsyncClient, employee: AsyncClient, project_id: str, login: Login
) -> None:
    outsider = await login("outsider")
    empty = (await metrics(manager, project_id)).json()

    assert (await metrics(employee, project_id)).status_code == 403
    assert (await metrics(outsider, project_id)).status_code == 404
    assert empty["assignment"]["top1_rate"] is None and empty["triage"]["cost"]["runs"] == 0
