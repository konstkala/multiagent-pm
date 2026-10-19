from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import anthropic
import httpx2
import pytest
from httpx import AsyncClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.agents.checkpoint import checkpointer
from app.agents.splitter.agent import Critique, SplitDraft, SubTicketDraft
from app.core.llm import LLMError
from app.db.models import Job
from app.services import splits
from app.services.embeddings import Embedder
from tests.fakes import FakeClaude, FakeParsed

pytestmark = pytest.mark.db

Checkpoints = Callable[[], AbstractAsyncContextManager[AsyncPostgresSaver]]


@pytest.fixture
def checkpoints(test_engine: AsyncEngine) -> Checkpoints:
    """LangGraph's checkpoint tables in the throwaway database, not the development one."""
    url = test_engine.url.render_as_string(hide_password=False)
    return lambda: checkpointer(url)


def proposal(*titles: str) -> FakeParsed:
    return FakeParsed(
        SplitDraft(
            sub_tickets=[
                SubTicketDraft(title=t, description=f"Do {t}.", story_points=3) for t in titles
            ],
            reason="by feature",
        )
    )


def verdict(ok: bool = True, *issues: str) -> FakeParsed:
    return FakeParsed(Critique(ok=ok, issues=list(issues)))


async def create(manager: AsyncClient, project_id: str, **fields: Any) -> dict[str, Any]:
    body = {
        "title": "Build billing",
        "description": "Invoices, payments, portal",
        "story_points": 13,
        "category": "implementation",
        "priority": "high",
        "labels": ["billing"],
    } | fields
    response = await manager.post(f"/projects/{project_id}/tickets", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def children(manager: AsyncClient, project_id: str, parent_id: str) -> list[dict[str, Any]]:
    response = await manager.get(f"/projects/{project_id}/tickets", params={"parent_id": parent_id})
    return response.json()["items"]


async def run_job(
    session: AsyncSession,
    split: dict[str, Any],
    claude: FakeClaude,
    embedder: Embedder,
    checkpoints: Checkpoints,
) -> None:
    await splits.run(
        session,
        {"run_id": split["id"]},
        llm=claude.client,
        embedder=embedder,
        checkpoints=checkpoints,
    )


async def current(manager: AsyncClient, ticket_id: str) -> dict[str, Any]:
    return (await manager.get(f"/tickets/{ticket_id}/split")).json()


# --- asking for a split ------------------------------------------------------------------------


async def test_only_a_manager_can_ask_for_a_split(
    manager: AsyncClient, employee: AsyncClient, project_id: str
) -> None:
    ticket = await create(manager, project_id)

    response = await employee.post(f"/tickets/{ticket['id']}/split")

    assert response.status_code == 403


async def test_small_tickets_and_sub_tasks_cannot_be_split(
    manager: AsyncClient, project_id: str
) -> None:
    small = await create(manager, project_id, story_points=5)
    parent = await create(manager, project_id)
    child = await create(manager, project_id, parent_id=parent["id"])

    responses = [await manager.post(f"/tickets/{t['id']}/split") for t in (small, child)]

    assert [r.status_code for r in responses] == [409, 409]


async def test_a_split_is_queued_as_an_interactive_job_and_only_one_runs_at_a_time(
    manager: AsyncClient, project_id: str, db_session: AsyncSession
) -> None:
    ticket = await create(manager, project_id)

    first = await manager.post(f"/tickets/{ticket['id']}/split")
    second = await manager.post(f"/tickets/{ticket['id']}/split")
    job = await db_session.scalar(select(Job).where(Job.kind == splits.JOB_KIND))

    assert (first.status_code, first.json()["status"]) == (202, "queued")
    assert second.status_code == 409
    assert job is not None and job.priority == 0  # a person is watching the screen


# --- the graph run, the pause and the decision -------------------------------------------------


async def test_split_pauses_for_the_manager_then_creates_only_what_they_keep(
    manager: AsyncClient,
    project_id: str,
    db_session: AsyncSession,
    embedder: Embedder,
    checkpoints: Checkpoints,
) -> None:
    ticket = await create(manager, project_id)
    split = (await manager.post(f"/tickets/{ticket['id']}/split")).json()

    claude = FakeClaude(proposal("Invoices", "Payments", "Portal"), verdict())
    await run_job(db_session, split, claude, embedder, checkpoints)
    paused = await current(manager, ticket["id"])

    assert paused["status"] == "proposed"
    assert [s["title"] for s in paused["proposal"]["sub_tickets"]] == [
        "Invoices",
        "Payments",
        "Portal",
    ]
    assert [c["node"] for c in paused["calls"]] == ["draft", "critique"]
    assert paused["cost_usd"] > 0 and paused["llm_calls"] == 2
    assert await children(manager, project_id, ticket["id"]) == []  # nothing created yet

    decided = await manager.post(f"/split-runs/{split['id']}/decide", json={"keep": [0, 2]})
    assert (decided.status_code, decided.json()["status"]) == (202, "resuming")

    resume = FakeClaude()  # resuming the graph must not call the model again
    await run_job(db_session, split, resume, embedder, checkpoints)
    done = await current(manager, ticket["id"])
    kids = await children(manager, project_id, ticket["id"])

    assert done["status"] == "applied" and resume.calls == []
    assert sorted(k["title"] for k in kids) == ["Invoices", "Portal"]
    assert {k["id"] for k in kids} == set(done["created_ticket_ids"])
    assert all(k["parent_id"] == ticket["id"] and k["category"] == "implementation" for k in kids)
    assert all(k["priority"] == "high" and k["labels"] == ["billing"] for k in kids)
    triage = [(await manager.get(f"/tickets/{k['id']}/triage")).json() for k in kids]
    assert [t["status"] for t in triage] == ["queued", "queued"]  # each child is triaged as usual


async def test_rejecting_the_proposal_creates_nothing(
    manager: AsyncClient,
    project_id: str,
    db_session: AsyncSession,
    embedder: Embedder,
    checkpoints: Checkpoints,
) -> None:
    ticket = await create(manager, project_id)
    split = (await manager.post(f"/tickets/{ticket['id']}/split")).json()
    await run_job(
        db_session, split, FakeClaude(proposal("A", "B"), verdict()), embedder, checkpoints
    )

    await manager.post(f"/split-runs/{split['id']}/decide", json={"keep": []})
    await run_job(db_session, split, FakeClaude(), embedder, checkpoints)

    assert (await current(manager, ticket["id"]))["status"] == "dismissed"
    assert await children(manager, project_id, ticket["id"]) == []


async def test_critic_issues_send_the_draft_back_for_one_revision(
    manager: AsyncClient,
    project_id: str,
    db_session: AsyncSession,
    embedder: Embedder,
    checkpoints: Checkpoints,
) -> None:
    ticket = await create(manager, project_id)
    split = (await manager.post(f"/tickets/{ticket['id']}/split")).json()
    claude = FakeClaude(
        proposal("Everything"),
        verdict(False, "Too coarse"),
        proposal("Invoices", "Payments"),
        verdict(),
    )

    await run_job(db_session, split, claude, embedder, checkpoints)
    run = await current(manager, ticket["id"])

    assert [c["node"] for c in run["calls"]] == ["draft", "critique", "revise", "critique"]
    assert run["rounds"] == 2 and run["proposal"]["issues"] == []
    assert [s["title"] for s in run["proposal"]["sub_tickets"]] == ["Invoices", "Payments"]


async def test_a_failed_attempt_continues_from_the_checkpoint_without_redrafting(
    manager: AsyncClient,
    project_id: str,
    db_session: AsyncSession,
    embedder: Embedder,
    checkpoints: Checkpoints,
) -> None:
    ticket = await create(manager, project_id)
    split = (await manager.post(f"/tickets/{ticket['id']}/split")).json()
    down = anthropic.APIConnectionError(
        request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    )

    with pytest.raises(LLMError):  # the draft is written, then the critic's call fails
        await run_job(
            db_session, split, FakeClaude(proposal("A", "B"), down), embedder, checkpoints
        )
    midway = await current(manager, ticket["id"])
    retry = FakeClaude(verdict())  # the queue retries the job: only the critic is called again
    await run_job(db_session, split, retry, embedder, checkpoints)
    run = await current(manager, ticket["id"])

    assert (midway["status"], midway["step"]) == ("running", "draft")
    assert (run["status"], len(retry.calls)) == ("proposed", 1)
    assert [c["node"] for c in run["calls"]] == ["draft", "critique"]


async def test_the_job_is_safe_to_run_twice(
    manager: AsyncClient,
    project_id: str,
    db_session: AsyncSession,
    embedder: Embedder,
    checkpoints: Checkpoints,
) -> None:
    ticket = await create(manager, project_id)
    split = (await manager.post(f"/tickets/{ticket['id']}/split")).json()
    await run_job(
        db_session, split, FakeClaude(proposal("A", "B"), verdict()), embedder, checkpoints
    )
    await manager.post(f"/split-runs/{split['id']}/decide", json={"keep": [0, 1]})
    await run_job(db_session, split, FakeClaude(), embedder, checkpoints)

    again = FakeClaude()
    await run_job(db_session, split, again, embedder, checkpoints)

    assert len(await children(manager, project_id, ticket["id"])) == 2
    assert again.calls == []


# --- guardrails --------------------------------------------------------------------------------


async def test_decisions_are_validated_and_only_possible_while_waiting(
    manager: AsyncClient,
    employee: AsyncClient,
    project_id: str,
    db_session: AsyncSession,
    embedder: Embedder,
    checkpoints: Checkpoints,
) -> None:
    ticket = await create(manager, project_id)
    split = (await manager.post(f"/tickets/{ticket['id']}/split")).json()
    url = f"/split-runs/{split['id']}/decide"

    too_early = await manager.post(url, json={"keep": [0]})
    await run_job(
        db_session, split, FakeClaude(proposal("A", "B"), verdict()), embedder, checkpoints
    )
    out_of_range = await manager.post(url, json={"keep": [2]})
    twice = await manager.post(url, json={"keep": [1, 1]})
    by_employee = await employee.post(url, json={"keep": [0]})
    fine = await manager.post(url, json={"keep": [1]})
    again = await manager.post(url, json={"keep": [0]})

    assert [r.status_code for r in (too_early, out_of_range, twice, by_employee, fine, again)] == [
        409,
        409,
        409,
        403,
        202,
        409,
    ]


async def test_a_refused_split_fails_with_a_short_code_and_creates_nothing(
    manager: AsyncClient,
    project_id: str,
    db_session: AsyncSession,
    embedder: Embedder,
    checkpoints: Checkpoints,
) -> None:
    ticket = await create(manager, project_id)
    split = (await manager.post(f"/tickets/{ticket['id']}/split")).json()

    await run_job(
        db_session,
        split,
        FakeClaude(FakeParsed(parsed_output=None, stop_reason="refusal")),
        embedder,
        checkpoints,
    )
    run = await current(manager, ticket["id"])

    assert (run["status"], run["error_code"]) == ("failed", "refused")
    assert await children(manager, project_id, ticket["id"]) == []
