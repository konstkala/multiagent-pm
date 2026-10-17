import json
import logging
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.cv_profile.agent import ProfileDraft, SkillDraft
from app.core.llm import LLMError
from app.db.models import Job
from app.main import app
from app.services import cv_imports
from app.services.storage import get_storage
from tests.fakes import FakeClaude, FakeParsed, MemoryStorage, minimal_pdf

pytestmark = pytest.mark.db

CV = minimal_pdf("Jane Doe", "Backend engineer, 6 years", "Python, PostgreSQL, FastAPI")
DRAFT = ProfileDraft(
    headline="Backend engineer",
    summary="Builds APIs.",
    years_experience=6,
    skills=[
        SkillDraft(name="Python", level=5, evidence="6 years"),
        SkillDraft(name="python", level=3, evidence="duplicate"),  # cleaned away
        SkillDraft(name="PostgreSQL", level=9, evidence="clamped to 5"),
    ],
)


@pytest.fixture
def storage(db_client: AsyncClient) -> MemoryStorage:
    fake = MemoryStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


async def ids(manager: AsyncClient, employee: AsyncClient) -> tuple[str, str]:
    workspace = (await manager.get("/workspaces")).json()[0]["id"]
    return workspace, (await employee.get("/auth/me")).json()["id"]


async def upload(client: AsyncClient, workspace: str, user: str, data: bytes = CV) -> Any:
    return await client.post(
        f"/workspaces/{workspace}/people/{user}/cv",
        files={"file": ("cv.pdf", data, "application/pdf")},
    )


async def run_job(
    session: AsyncSession, storage: MemoryStorage, import_id: str, claude: FakeClaude
) -> None:
    await cv_imports.run(session, {"import_id": import_id}, llm=claude.client, storage=storage)


# --- profiles --------------------------------------------------------------------------------


async def test_managers_see_people_employees_see_only_themselves(
    manager: AsyncClient, employee: AsyncClient
) -> None:
    workspace, emp = await ids(manager, employee)
    me = (await manager.get("/auth/me")).json()["id"]

    people = await manager.get(f"/workspaces/{workspace}/people")
    own = await employee.get(f"/workspaces/{workspace}/people/{emp}/profile")
    others = await employee.get(f"/workspaces/{workspace}/people/{me}/profile")
    listing = await employee.get(f"/workspaces/{workspace}/people")

    assert {p["display_name"] for p in people.json()} == {"Manager", "Emp"}
    assert own.status_code == 200
    assert own.json()["updated_at"] is None  # nobody filled it in yet
    assert others.status_code == listing.status_code == 403


async def test_manager_saves_a_profile(manager: AsyncClient, employee: AsyncClient) -> None:
    workspace, emp = await ids(manager, employee)
    url = f"/workspaces/{workspace}/people/{emp}/profile"

    saved = await manager.put(
        url,
        json={
            "headline": "Backend engineer",
            "years_experience": 6,
            "skills": [{"name": "Python", "level": 5}, {"name": "SQL", "level": 3}],
        },
    )
    duplicate = await manager.put(
        url, json={"skills": [{"name": "Go", "level": 2}, {"name": "go", "level": 3}]}
    )
    bad_level = await manager.put(url, json={"skills": [{"name": "Go", "level": 6}]})
    by_employee = await employee.put(url, json={"headline": "CEO"})

    assert saved.status_code == 200
    assert [(s["name"], s["level"]) for s in saved.json()["skills"]] == [("Python", 5), ("SQL", 3)]
    assert duplicate.status_code == bad_level.status_code == 422
    assert by_employee.status_code == 403


# --- CV import: upload -----------------------------------------------------------------------


async def test_cv_upload_is_queued_for_the_agent(
    manager: AsyncClient, employee: AsyncClient, storage: MemoryStorage, db_session: AsyncSession
) -> None:
    workspace, emp = await ids(manager, employee)

    response = await upload(manager, workspace, emp)
    job = await db_session.scalar(select(Job).where(Job.kind == "cv_import"))

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert job is not None and job.payload == {"import_id": response.json()["id"]}
    assert len(storage.objects) == 1


async def test_cv_upload_rules(
    manager: AsyncClient, employee: AsyncClient, storage: MemoryStorage
) -> None:
    workspace, emp = await ids(manager, employee)

    not_pdf = await upload(manager, workspace, emp, b"<html>CV</html>")
    too_big = await upload(manager, workspace, emp, CV + b"0" * (5 * 2**20))
    by_employee = await upload(employee, workspace, emp)

    assert not_pdf.status_code == 422
    assert too_big.status_code == 413
    assert by_employee.status_code == 403
    assert storage.objects == {}


# --- CV import: the agent run ----------------------------------------------------------------


async def test_agent_run_produces_a_clean_draft_and_deletes_the_cv(
    manager: AsyncClient,
    employee: AsyncClient,
    storage: MemoryStorage,
    db_session: AsyncSession,
) -> None:
    workspace, emp = await ids(manager, employee)
    import_id = (await upload(manager, workspace, emp)).json()["id"]
    claude = FakeClaude(FakeParsed(parsed_output=DRAFT))

    await run_job(db_session, storage, import_id, claude)
    result = (await manager.get(f"/cv-imports/{import_id}")).json()

    call = claude.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["output_config"] == {"effort": "low"}
    assert call["messages"][0]["content"][0]["type"] == "document"  # the PDF itself
    assert result["status"] == "needs_review"
    assert [(s["name"], s["level"]) for s in result["draft"]["skills"]] == [
        ("Python", 5),
        ("PostgreSQL", 5),
    ]
    assert result["cost_usd"] > 0
    assert result["model"] == "claude-haiku-5-5"
    assert storage.objects == {}  # GDPR: the CV is gone


async def test_agent_run_is_safe_to_repeat(
    manager: AsyncClient,
    employee: AsyncClient,
    storage: MemoryStorage,
    db_session: AsyncSession,
) -> None:
    workspace, emp = await ids(manager, employee)
    import_id = (await upload(manager, workspace, emp)).json()["id"]
    claude = FakeClaude(FakeParsed(parsed_output=DRAFT))

    await run_job(db_session, storage, import_id, claude)
    await run_job(db_session, storage, import_id, claude)  # e.g. redelivered job

    assert len(claude.calls) == 1


async def test_refusal_fails_at_once_and_deletes_the_cv(
    manager: AsyncClient,
    employee: AsyncClient,
    storage: MemoryStorage,
    db_session: AsyncSession,
) -> None:
    workspace, emp = await ids(manager, employee)
    import_id = (await upload(manager, workspace, emp)).json()["id"]

    await run_job(
        db_session, storage, import_id, FakeClaude(FakeParsed(None, stop_reason="refusal"))
    )
    result = (await manager.get(f"/cv-imports/{import_id}")).json()

    assert (result["status"], result["error_code"]) == ("failed", "refused")
    assert storage.objects == {}


async def test_transient_errors_retry_then_give_up(
    manager: AsyncClient,
    employee: AsyncClient,
    storage: MemoryStorage,
    db_session: AsyncSession,
) -> None:
    workspace, emp = await ids(manager, employee)
    import_id = (await upload(manager, workspace, emp)).json()["id"]
    claude = FakeClaude(*(LLMError("overloaded") for _ in range(3)))

    for _ in range(2):
        with pytest.raises(LLMError):  # the worker sees it and schedules a retry
            await run_job(db_session, storage, import_id, claude)
        assert len(storage.objects) == 1  # kept for the next attempt
    await run_job(db_session, storage, import_id, claude)
    result = (await manager.get(f"/cv-imports/{import_id}")).json()

    assert (result["status"], result["error_code"]) == ("failed", "ai_unavailable")
    assert storage.objects == {}


# --- review ----------------------------------------------------------------------------------


async def needs_review(
    manager: AsyncClient,
    employee: AsyncClient,
    storage: MemoryStorage,
    db_session: AsyncSession,
) -> tuple[str, str, str]:
    workspace, emp = await ids(manager, employee)
    import_id = (await upload(manager, workspace, emp)).json()["id"]
    await run_job(db_session, storage, import_id, FakeClaude(FakeParsed(parsed_output=DRAFT)))
    return workspace, emp, import_id


async def test_approving_saves_the_edited_profile_and_drops_the_draft(
    manager: AsyncClient,
    employee: AsyncClient,
    storage: MemoryStorage,
    db_session: AsyncSession,
) -> None:
    workspace, emp, import_id = await needs_review(manager, employee, storage, db_session)

    approved = await manager.post(
        f"/cv-imports/{import_id}/approve",
        json={"headline": "Senior backend engineer", "skills": [{"name": "Python", "level": 4}]},
    )
    again = await manager.post(f"/cv-imports/{import_id}/approve", json={})
    profile = (await employee.get(f"/workspaces/{workspace}/people/{emp}/profile")).json()

    assert approved.json()["status"] == "approved"
    assert approved.json()["draft"] is None
    assert again.status_code == 409
    assert profile["headline"] == "Senior backend engineer"
    assert profile["skills"] == [{"name": "Python", "level": 4}]


async def test_rejecting_drops_the_draft_and_keeps_the_profile(
    manager: AsyncClient,
    employee: AsyncClient,
    storage: MemoryStorage,
    db_session: AsyncSession,
) -> None:
    workspace, emp, import_id = await needs_review(manager, employee, storage, db_session)

    rejected = (await manager.post(f"/cv-imports/{import_id}/reject")).json()
    profile = (await employee.get(f"/workspaces/{workspace}/people/{emp}/profile")).json()

    assert (rejected["status"], rejected["draft"]) == ("rejected", None)
    assert profile["skills"] == []


async def test_employees_cannot_see_or_decide_imports(
    manager: AsyncClient,
    employee: AsyncClient,
    storage: MemoryStorage,
    db_session: AsyncSession,
) -> None:
    _, _, import_id = await needs_review(manager, employee, storage, db_session)

    seen = await employee.get(f"/cv-imports/{import_id}")
    approved = await employee.post(f"/cv-imports/{import_id}/approve", json={})

    assert seen.status_code == approved.status_code == 403


async def test_logs_carry_no_cv_content(
    manager: AsyncClient,
    employee: AsyncClient,
    storage: MemoryStorage,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    _, _, import_id = await needs_review(manager, employee, storage, db_session)
    await manager.post(
        f"/cv-imports/{import_id}/approve",
        json={"headline": "Backend engineer", "skills": [{"name": "PostgreSQL", "level": 5}]},
    )

    logged = json.dumps([r.__dict__.get("fields", {}) for r in caplog.records], default=str)
    events = [r.getMessage() for r in caplog.records]
    assert "PostgreSQL" not in logged
    assert "Backend engineer" not in logged
    assert {"cv_import.extracted", "audit.cv_import.approved", "audit.profile.saved"} <= set(events)
