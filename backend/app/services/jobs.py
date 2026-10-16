"""Postgres job queue (ADR 0010): at-least-once delivery, so handlers must be safe to repeat."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, JobStatus

STALE_AFTER = timedelta(minutes=10)  # a running job this old belongs to a worker that died
BACKOFF = timedelta(seconds=30)  # 30 s, 60 s, 120 s, ...


def enqueue(session: AsyncSession, kind: str, payload: dict[str, Any]) -> Job:
    """Adds a job to the caller's transaction: it exists only if the caller's change commits."""
    job = Job(kind=kind, payload=payload)
    session.add(job)
    return job


async def claim(session: AsyncSession) -> Job | None:
    """Takes the oldest runnable job for this worker, or None. Safe with many workers at once."""
    now = datetime.now(UTC)
    stale = and_(Job.status == JobStatus.RUNNING, Job.locked_at < now - STALE_AFTER)
    # A crashed worker's job with no attempts left would otherwise stay "running" forever.
    await session.execute(
        update(Job)
        .where(stale, Job.attempts >= Job.max_attempts)
        .values(status=JobStatus.FAILED, finished_at=now, last_error="WorkerLost")
    )
    runnable = or_(
        and_(Job.status == JobStatus.QUEUED, Job.run_after <= now),
        and_(stale, Job.attempts < Job.max_attempts),
    )
    # SKIP LOCKED: rows another worker is claiming right now are skipped, not waited for.
    next_id = (
        select(Job.id)
        .where(runnable)
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    job = await session.scalar(
        update(Job)
        .where(Job.id == next_id)
        .values(status=JobStatus.RUNNING, attempts=Job.attempts + 1, locked_at=now)
        .returning(Job)
    )
    await session.commit()
    return job


async def complete(session: AsyncSession, job: Job) -> None:
    job.status = JobStatus.SUCCEEDED
    job.locked_at = None
    job.finished_at = datetime.now(UTC)
    await session.commit()


async def fail(session: AsyncSession, job: Job, error: str, *, permanent: bool = False) -> bool:
    """Schedules a retry with backoff, or gives up. Returns True if the job will run again."""
    now = datetime.now(UTC)
    job.locked_at = None
    job.last_error = error[:200]
    retry = not permanent and job.attempts < job.max_attempts
    if retry:
        job.status = JobStatus.QUEUED
        job.run_after = now + BACKOFF * 2 ** (job.attempts - 1)
    else:
        job.status = JobStatus.FAILED
        job.finished_at = now
    await session.commit()
    return retry
