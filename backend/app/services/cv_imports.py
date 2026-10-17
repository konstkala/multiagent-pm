"""CV import: upload → background extraction by the CV agent → a manager approves or rejects."""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.cv_profile.agent import extract_profile
from app.core.config import settings
from app.core.errors import (
    ConflictError,
    FileTooLargeError,
    InvalidRequestError,
    NotFoundError,
    StorageUnavailableError,
)
from app.core.llm import BudgetExceededError, LLMClient, LLMError, LLMRefusalError, RunBudget
from app.core.logging import log_fields
from app.db.models import CvImport, CvImportStatus, User
from app.schemas.profiles import ProfileWrite
from app.services import jobs, profiles
from app.services.file_types import detect_content_type
from app.services.storage import Storage, StorageError

logger = logging.getLogger(__name__)

JOB_KIND = "cv_import"
MAX_ATTEMPTS = 3  # same as the job queue: after this, give up and delete the CV


async def start(
    session: AsyncSession,
    storage: Storage,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    data: bytes,
    actor: User,
) -> CvImport:
    await profiles.require_people_manager(session, workspace_id, actor)
    await profiles.get_profile(session, workspace_id, user_id, actor)  # target must be a member
    if len(data) > settings.cv_max_bytes:
        raise FileTooLargeError(f"CVs can be at most {settings.cv_max_bytes // 2**20} MB")
    if detect_content_type("cv.pdf", data) != "application/pdf":  # checks the PDF signature
        raise InvalidRequestError("Upload the CV as a PDF")

    cv_import = CvImport(
        workspace_id=workspace_id, user_id=user_id, requested_by=actor.id, size_bytes=len(data)
    )
    session.add(cv_import)
    await session.flush()
    key = f"cv/{cv_import.id}"
    try:
        await storage.put(key, data, "application/pdf")
    except StorageError as exc:
        await session.rollback()
        raise StorageUnavailableError("File storage is unavailable. Try again shortly.") from exc
    cv_import.storage_key = key
    # Same transaction: the job exists exactly when the import does.
    jobs.enqueue(session, JOB_KIND, {"import_id": str(cv_import.id)})
    await session.commit()
    await session.refresh(cv_import)
    logger.info(
        "audit.cv_import.started",
        extra=log_fields(actor=actor.id, import_id=cv_import.id, size_bytes=len(data)),
    )
    return cv_import


async def get(session: AsyncSession, import_id: uuid.UUID, actor: User) -> CvImport:
    cv_import = await session.get(CvImport, import_id)
    if cv_import is None:
        raise NotFoundError("CV import not found")
    try:
        await profiles.require_people_manager(session, cv_import.workspace_id, actor)
    except NotFoundError as exc:
        raise NotFoundError("CV import not found") from exc
    return cv_import


async def list_for_workspace(
    session: AsyncSession, workspace_id: uuid.UUID, actor: User
) -> list[CvImport]:
    await profiles.require_people_manager(session, workspace_id, actor)
    rows = await session.scalars(
        select(CvImport)
        .where(CvImport.workspace_id == workspace_id)
        .order_by(CvImport.created_at.desc())
        .limit(50)
    )
    return list(rows)


async def approve(
    session: AsyncSession, import_id: uuid.UUID, data: ProfileWrite, actor: User
) -> CvImport:
    """Saves the (possibly edited) draft as the profile; the draft itself is then deleted."""
    cv_import = await _awaiting_review(session, import_id, actor)
    await profiles.save_profile(
        session, cv_import.workspace_id, cv_import.user_id, data, actor, commit=False
    )
    _decide(cv_import, CvImportStatus.APPROVED)
    await session.commit()
    logger.info("audit.cv_import.approved", extra=log_fields(actor=actor.id, import_id=import_id))
    return cv_import


async def reject(session: AsyncSession, import_id: uuid.UUID, actor: User) -> CvImport:
    cv_import = await _awaiting_review(session, import_id, actor)
    _decide(cv_import, CvImportStatus.REJECTED)
    await session.commit()
    logger.info("audit.cv_import.rejected", extra=log_fields(actor=actor.id, import_id=import_id))
    return cv_import


async def run(
    session: AsyncSession,
    payload: dict[str, Any],
    *,
    llm: Callable[[], LLMClient],
    storage: Storage,
) -> None:
    """The job. Safe to run twice: anything but a queued import is left alone."""
    cv_import = await session.get(CvImport, uuid.UUID(str(payload["import_id"])))
    if cv_import is None or cv_import.status is not CvImportStatus.QUEUED:
        return
    cv_import.attempts += 1
    await session.commit()

    try:
        if cv_import.storage_key is None:
            raise _Permanent("cv_missing")
        pdf = await storage.get(cv_import.storage_key)
        result = await extract_profile(llm(), pdf, RunBudget(run_id=str(cv_import.id)))
    except (LLMRefusalError, BudgetExceededError) as exc:
        await _give_up(session, storage, cv_import, _error_code(exc))  # retrying won't help
        return
    except _Permanent as exc:
        await _give_up(session, storage, cv_import, exc.code)
        return
    except (LLMError, StorageError) as exc:
        if cv_import.attempts >= MAX_ATTEMPTS:
            await _give_up(session, storage, cv_import, _error_code(exc))
            return
        raise  # the queue retries with backoff; the CV stays for the next attempt

    cv_import.draft = result.output.model_dump(mode="json")
    cv_import.model = result.model
    cv_import.cost_usd = result.cost_usd
    cv_import.latency_ms = result.latency_ms
    cv_import.status = CvImportStatus.NEEDS_REVIEW
    cv_import.processed_at = datetime.now(UTC)
    await session.commit()
    await _delete_cv(session, storage, cv_import)
    logger.info(
        "cv_import.extracted",
        extra=log_fields(
            import_id=cv_import.id,
            skill_count=len(result.output.skills),
            cost_usd=round(result.cost_usd, 6),
            latency_ms=result.latency_ms,
        ),
    )


class _Permanent(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def _awaiting_review(session: AsyncSession, import_id: uuid.UUID, actor: User) -> CvImport:
    cv_import = await get(session, import_id, actor)
    if cv_import.status is not CvImportStatus.NEEDS_REVIEW:
        raise ConflictError(f"This CV import is {cv_import.status.value.replace('_', ' ')}")
    return cv_import


def _decide(cv_import: CvImport, status: CvImportStatus) -> None:
    cv_import.status = status
    cv_import.draft = None  # personal data is kept only until a person decides
    cv_import.decided_at = datetime.now(UTC)


async def _give_up(session: AsyncSession, storage: Storage, cv_import: CvImport, code: str) -> None:
    cv_import.status = CvImportStatus.FAILED
    cv_import.error_code = code
    cv_import.processed_at = datetime.now(UTC)
    await session.commit()
    await _delete_cv(session, storage, cv_import)
    logger.warning("cv_import.failed", extra=log_fields(import_id=cv_import.id, error=code))


async def _delete_cv(session: AsyncSession, storage: Storage, cv_import: CvImport) -> None:
    """GDPR: the CV is needed only for extraction."""
    if cv_import.storage_key is None:
        return
    try:
        await storage.delete(cv_import.storage_key)
    except StorageError:
        logger.exception("storage.orphan_object", extra=log_fields(import_id=cv_import.id))
        return
    cv_import.storage_key = None
    await session.commit()


def _error_code(exc: Exception) -> str:
    """A short code the manager sees. Never the exception text: it could echo CV content."""
    if isinstance(exc, LLMRefusalError):
        return "refused"
    if isinstance(exc, BudgetExceededError):
        return "over_budget"
    if isinstance(exc, StorageError):
        return "storage_unavailable"
    return "ai_unavailable"
