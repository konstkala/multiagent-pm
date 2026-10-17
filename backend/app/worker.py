"""Background worker: `python -m app.worker`. Runs queued jobs until told to stop."""

import asyncio
import logging
import signal
import time
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, suppress
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import LLMClient, create_llm_client
from app.core.logging import configure_logging, log_fields, run_id_var
from app.db.session import SessionLocal, engine
from app.services import cv_imports, jobs
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class Worker:
    def __init__(
        self,
        sessions: SessionFactory,
        handlers: Mapping[str, Handler],
        poll_interval: float = 2.0,
    ) -> None:
        self._sessions = sessions
        self._handlers = handlers
        self._poll_interval = poll_interval

    async def run(self, stop: asyncio.Event) -> None:
        logger.info("worker.started", extra=log_fields(kinds=sorted(self._handlers)))
        while not stop.is_set():
            if not await self.run_once():
                # Nothing to do: sleep, but wake at once on shutdown.
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=self._poll_interval)
        logger.info("worker.stopped")

    async def run_once(self) -> bool:
        """Runs at most one job. Returns False when the queue had nothing runnable."""
        async with self._sessions() as session:
            job = await jobs.claim(session)
            if job is None:
                return False
            token = run_id_var.set(str(job.id))
            started = time.perf_counter()
            fields = {"job_id": job.id, "kind": job.kind, "attempt": job.attempts}
            try:
                handler = self._handlers.get(job.kind)
                if handler is None:
                    logger.error("job.unknown_kind", extra=log_fields(**fields))
                    await jobs.fail(session, job, "UnknownKind", permanent=True)
                    return True
                logger.info("job.started", extra=log_fields(**fields))
                # The handler gets its own session, so its transaction is separate from the job's.
                async with self._sessions() as work_session:
                    await handler(work_session, job.payload)
                await jobs.complete(session, job)
                logger.info(
                    "job.succeeded",
                    extra=log_fields(**fields, duration_ms=_elapsed_ms(started)),
                )
            except Exception as exc:  # a job must never take the worker down with it
                retry = await jobs.fail(session, job, type(exc).__name__)
                logger.exception(
                    "job.failed",
                    extra=log_fields(**fields, will_retry=retry, duration_ms=_elapsed_ms(started)),
                )
            finally:
                run_id_var.reset(token)
            return True


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


@lru_cache(maxsize=1)
def _llm() -> LLMClient:
    # Created on first use: a worker without an API key still runs non-AI jobs.
    return create_llm_client()


def handlers() -> dict[str, Handler]:
    """Job kinds this worker runs. Each feature registers its handler here."""

    async def cv_import(session: AsyncSession, payload: dict[str, Any]) -> None:
        await cv_imports.run(session, payload, llm=_llm, storage=get_storage())

    return {cv_imports.JOB_KIND: cv_import}


async def main() -> None:
    configure_logging(settings.log_level)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        # SIGTERM is what `docker stop` and Kubernetes send: finish the job, then exit.
        # Windows has no signal handlers in asyncio; Ctrl+C still stops it there.
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
    try:
        await Worker(SessionLocal, handlers()).run(stop)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
