import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.models import Job, JobStatus
from app.services import jobs
from app.worker import Handler, Worker

pytestmark = pytest.mark.db


def worker_for(session: AsyncSession, handlers: dict[str, Handler]) -> Worker:
    @asynccontextmanager
    async def shared() -> AsyncGenerator[AsyncSession]:
        yield session  # tests share one rolled-back session

    return Worker(shared, handlers, poll_interval=0.01)


async def add_job(session: AsyncSession, kind: str = "noop", **fields: Any) -> Job:
    job = jobs.enqueue(session, kind, {"n": 1})
    for name, value in fields.items():
        setattr(job, name, value)
    await session.commit()
    return job


async def test_claim_takes_the_oldest_runnable_job(db_session: AsyncSession) -> None:
    first = await add_job(db_session)
    await add_job(db_session)
    await add_job(db_session, run_after=datetime.now(UTC) + timedelta(hours=1))  # not yet

    claimed = [await jobs.claim(db_session) for _ in range(3)]

    assert claimed[0] is not None and claimed[0].id == first.id
    assert claimed[0].status is JobStatus.RUNNING
    assert claimed[0].attempts == 1
    assert claimed[1] is not None
    assert claimed[2] is None  # the future job waits


async def test_failures_retry_with_growing_backoff_then_give_up(db_session: AsyncSession) -> None:
    job = await add_job(db_session)
    delays: list[timedelta] = []
    retry = True
    while retry:
        claimed = await jobs.claim(db_session)
        assert claimed is not None and claimed.id == job.id
        retry = await jobs.fail(db_session, claimed, "Boom")
        delays.append(claimed.run_after - datetime.now(UTC))
        # Skip the wait: a second in the past, so the next claim never races the clock.
        claimed.run_after = datetime.now(UTC) - timedelta(seconds=1)
        await db_session.commit()

    assert job.status is JobStatus.FAILED
    assert job.attempts == 3
    assert job.last_error == "Boom"
    assert delays[1] > delays[0]


async def test_job_of_a_dead_worker_is_picked_up_again(db_session: AsyncSession) -> None:
    long_ago = datetime.now(UTC) - timedelta(hours=1)
    lost = await add_job(db_session, status=JobStatus.RUNNING, locked_at=long_ago, attempts=1)
    exhausted = await add_job(db_session, status=JobStatus.RUNNING, locked_at=long_ago, attempts=3)

    claimed = await jobs.claim(db_session)
    await db_session.refresh(exhausted)

    assert claimed is not None and claimed.id == lost.id
    assert claimed.attempts == 2
    assert exhausted.status is JobStatus.FAILED


async def test_concurrent_workers_never_claim_the_same_job(test_engine: AsyncEngine) -> None:
    """Real commits on separate connections: this is what SKIP LOCKED is for."""
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sessions() as setup:
        created = [jobs.enqueue(setup, "concurrency-test", {}) for _ in range(5)]
        await setup.commit()
    try:

        async def one_worker() -> list[str]:
            got: list[str] = []
            async with sessions() as session:
                while job := await jobs.claim(session):
                    if job.kind == "concurrency-test":
                        got.append(str(job.id))
            return got

        results = await asyncio.gather(*(one_worker() for _ in range(4)))
        claimed = [job_id for result in results for job_id in result]

        assert sorted(claimed) == sorted(str(j.id) for j in created)  # each exactly once
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(Job).where(Job.kind == "concurrency-test"))
            await cleanup.commit()


async def test_worker_runs_handler_and_records_success(db_session: AsyncSession) -> None:
    seen: list[dict[str, Any]] = []

    async def handler(_: AsyncSession, payload: dict[str, Any]) -> None:
        seen.append(payload)

    job = await add_job(db_session, kind="ok")

    processed = await worker_for(db_session, {"ok": handler}).run_once()

    assert processed is True
    assert seen == [{"n": 1}]
    assert job.status is JobStatus.SUCCEEDED
    assert job.finished_at is not None


async def test_handler_error_is_retried_and_logged_with_run_id(
    db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.worker")

    async def broken(_: AsyncSession, __: dict[str, Any]) -> None:
        raise RuntimeError("model said no")

    job = await add_job(db_session, kind="broken")

    await worker_for(db_session, {"broken": broken}).run_once()

    assert job.status is JobStatus.QUEUED  # will retry
    assert job.last_error == "RuntimeError"
    failed = next(r for r in caplog.records if r.getMessage() == "job.failed")
    assert failed.__dict__["fields"]["will_retry"] is True
    assert "model said no" not in json.dumps(failed.__dict__["fields"], default=str)


async def test_unknown_job_kind_fails_permanently(db_session: AsyncSession) -> None:
    job = await add_job(db_session, kind="who-knows")

    await worker_for(db_session, {}).run_once()

    assert job.status is JobStatus.FAILED


async def test_worker_loop_stops_when_asked(db_session: AsyncSession) -> None:
    stop = asyncio.Event()
    worker = worker_for(db_session, {})

    task = asyncio.create_task(worker.run(stop))
    await asyncio.sleep(0.05)
    stop.set()

    await asyncio.wait_for(task, timeout=1)  # returns promptly, no hang
