"""Triage runs (ADR 0016): the agent proposes, a manager answers, accepts or dismisses."""

import logging
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.triage.agent import Image, SimilarTicket, TriageInput, TriageProposal, triage
from app.core.errors import ConflictError, NotFoundError
from app.core.llm import (
    BudgetExceededError,
    LLMClient,
    LLMError,
    LLMRefusalError,
    LLMRequestRejectedError,
    RunBudget,
    StructuredResult,
)
from app.core.llm.content import ImageType
from app.core.logging import log_fields
from app.db.models import (
    Project,
    Ticket,
    TicketAttachment,
    TriageRun,
    TriageStatus,
    TriageTrigger,
    User,
)
from app.schemas.tickets import TicketUpdate
from app.schemas.triage import TriageAccept
from app.services import access, jobs, triage_queue
from app.services.storage import Storage, StorageError
from app.services.tickets import get_ticket, update_ticket

logger = logging.getLogger(__name__)

AGENT = "triage-agent"  # the actor in audit logs for changes the agent makes itself
AUTO_APPLY_CONFIDENCE = 0.7
MAX_ATTEMPTS = 3
SIMILAR_LIMIT = 5
SIMILAR_MIN = 0.6
MAX_IMAGES = 3
MAX_IMAGE_BYTES = 5 * 2**20  # Claude's limit per image
# Stored content type -> the exact type Claude accepts.
_IMAGE_TYPES: dict[str, ImageType] = {
    "image/png": "image/png",
    "image/jpeg": "image/jpeg",
    "image/gif": "image/gif",
    "image/webp": "image/webp",
}


async def latest(session: AsyncSession, ticket_id: uuid.UUID, user: User) -> TriageRun | None:
    await get_ticket(session, ticket_id, user)  # any project member may look
    return await session.scalar(
        select(TriageRun)
        .where(TriageRun.ticket_id == ticket_id)
        .order_by(TriageRun.created_at.desc())
        .limit(1)
    )


async def rerun(session: AsyncSession, ticket_id: uuid.UUID, actor: User) -> TriageRun:
    ticket = await get_ticket(session, ticket_id, actor)
    await access.require_manager(session, ticket.project_id, actor)
    open_run = await session.scalar(
        select(TriageRun.id).where(
            TriageRun.ticket_id == ticket_id,
            TriageRun.status.in_([TriageStatus.QUEUED, TriageStatus.NEEDS_ANSWER]),
        )
    )
    if open_run is not None:
        raise ConflictError("Triage is already running for this ticket")
    run = await triage_queue.enqueue(session, ticket, TriageTrigger.MANUAL)
    if run is None:
        raise ConflictError("Triage is switched off")
    await session.commit()
    logger.info("audit.triage.rerun", extra=log_fields(actor=actor.id, run_id=run.id))
    return run


async def answer(session: AsyncSession, run_id: uuid.UUID, text_: str, actor: User) -> TriageRun:
    run = await _managed_run(session, run_id, actor, TriageStatus.NEEDS_ANSWER)
    run.answer = text_
    run.status = TriageStatus.QUEUED
    jobs.enqueue(session, triage_queue.JOB_KIND, {"run_id": str(run.id)})
    await session.commit()
    logger.info(
        "audit.triage.answered",
        extra=log_fields(actor=actor.id, triage_run_id=run.id, answer_len=len(text_)),
    )
    return run


async def accept(
    session: AsyncSession, run_id: uuid.UUID, changes: TriageAccept, actor: User
) -> TriageRun:
    """Applies what the manager kept (possibly edited) through the normal ticket update path."""
    run = await _managed_run(session, run_id, actor, TriageStatus.PROPOSED)
    run.status = TriageStatus.APPLIED
    run.accepted = changes.model_dump(mode="json", exclude_unset=True)
    run.decided_by = actor.id
    run.decided_at = datetime.now(UTC)
    # update_ticket checks permissions and values, writes the audit log and commits both.
    update = TicketUpdate.model_validate(changes.model_dump(exclude_unset=True))
    await update_ticket(session, run.ticket_id, update, actor, embedder=None)
    logger.info(
        "audit.triage.accepted",
        extra=log_fields(
            actor=actor.id, triage_run_id=run.id, fields=sorted(changes.model_fields_set)
        ),
    )
    return run


async def dismiss(session: AsyncSession, run_id: uuid.UUID, actor: User) -> TriageRun:
    run = await _managed_run(
        session, run_id, actor, TriageStatus.PROPOSED, TriageStatus.NEEDS_ANSWER
    )
    run.status = TriageStatus.DISMISSED
    run.decided_by = actor.id
    run.decided_at = datetime.now(UTC)
    await session.commit()
    logger.info("audit.triage.dismissed", extra=log_fields(actor=actor.id, triage_run_id=run.id))
    return run


async def run(
    session: AsyncSession,
    payload: dict[str, Any],
    *,
    llm: Callable[[], LLMClient],
    storage: Storage,
) -> None:
    """The job. Safe to run twice: anything but a queued run is left alone."""
    triage_run = await session.get(TriageRun, uuid.UUID(str(payload["run_id"])))
    if triage_run is None or triage_run.status is not TriageStatus.QUEUED:
        return
    ticket = await session.get(Ticket, triage_run.ticket_id)
    project = await session.get(Project, ticket.project_id) if ticket else None
    if ticket is None or project is None:
        await _fail(session, triage_run, "ticket_missing")
        return
    triage_run.attempts += 1
    await session.commit()

    budget = RunBudget(run_id=str(triage_run.id))
    budget.record(triage_run.cost_usd)  # a second round (after a question) shares the cap
    try:
        similar = await _similar(session, ticket)
        data = TriageInput(
            key=f"{project.key}-{ticket.number}",
            title=ticket.title,
            description=ticket.description,
            similar=similar,
            project_labels=await _project_labels(session, project.id),
            images=await _images(session, storage, ticket.id),
            question=triage_run.question,
            answer=triage_run.answer,
        )
        result = await _triage_dropping_bad_images(llm(), data, budget, triage_run.id)
    except (LLMRefusalError, BudgetExceededError, LLMRequestRejectedError) as exc:
        await _fail(session, triage_run, _error_code(exc))  # retrying won't help
        return
    except (LLMError, StorageError) as exc:
        if triage_run.attempts >= MAX_ATTEMPTS:
            await _fail(session, triage_run, _error_code(exc))
            return
        raise  # the queue retries with backoff

    triage_run.model = result.model
    triage_run.llm_calls += 1
    triage_run.cost_usd += result.cost_usd
    triage_run.latency_ms += result.latency_ms
    proposal = result.output
    if proposal.question:
        triage_run.question = proposal.question
        triage_run.status = TriageStatus.NEEDS_ANSWER
        await session.commit()
        logger.info("triage.question_asked", extra=log_fields(triage_run_id=triage_run.id))
        return

    triage_run.proposal = _stored(proposal, similar)
    triage_run.auto_applied = _auto_apply(ticket, proposal)
    triage_run.status = TriageStatus.PROPOSED
    triage_run.finished_at = datetime.now(UTC)
    await session.commit()
    logger.info(
        "triage.proposed",
        extra=log_fields(
            triage_run_id=triage_run.id,
            ticket_id=ticket.id,
            classification_confidence=proposal.classification_confidence,
            sizing_confidence=proposal.sizing_confidence,
            llm_calls=triage_run.llm_calls,
            cost_usd=round(triage_run.cost_usd, 6),
        ),
    )
    if triage_run.auto_applied:
        logger.info(
            "audit.ticket.updated",
            extra=log_fields(
                actor=AGENT,
                triage_run_id=triage_run.id,
                ticket_id=ticket.id,
                changed_fields=triage_run.auto_applied,
                after={"category": ticket.category, "labels": ticket.labels},
            ),
        )


def _auto_apply(ticket: Ticket, proposal: TriageProposal) -> list[str]:
    """Only cheap-to-undo fields, only when confident, and never over a person's choice."""
    if proposal.classification_confidence < AUTO_APPLY_CONFIDENCE:
        return []
    applied: list[str] = []
    if ticket.category is None:
        ticket.category = proposal.category
        applied.append("category")
    if not ticket.labels and proposal.labels:
        ticket.labels = proposal.labels
        applied.append("labels")
    return applied


def _stored(proposal: TriageProposal, similar: list[SimilarTicket]) -> dict[str, Any]:
    stored = proposal.model_dump(mode="json")
    # The model works with ticket numbers; the API needs the id to apply a duplicate.
    duplicate = next((t for t in similar if t.number == proposal.duplicate_of), None)
    stored["duplicate_of_id"] = str(duplicate.id) if duplicate else None
    stored["duplicate_of_title"] = duplicate.title if duplicate else None
    return stored


async def _similar(session: AsyncSession, ticket: Ticket) -> list[SimilarTicket]:
    if ticket.embedding is None:
        return []
    distance = Ticket.embedding.cosine_distance(ticket.embedding)
    rows = await session.execute(
        select(Ticket, (1 - distance).label("similarity"))
        .where(
            Ticket.id != ticket.id,
            Ticket.project_id == ticket.project_id,
            Ticket.embedding_model == ticket.embedding_model,
            distance <= 1 - SIMILAR_MIN,
        )
        .order_by(distance)
        .limit(SIMILAR_LIMIT)
    )
    return [
        SimilarTicket(
            id=other.id,
            number=other.number,
            title=other.title,
            status=other.status.value,
            category=other.category.value if other.category else None,
            story_points=other.story_points,
            similarity=float(similarity),
        )
        for other, similarity in rows
    ]


async def _project_labels(session: AsyncSession, project_id: uuid.UUID) -> list[str]:
    """The project's labels, most used first, so the agent reuses them instead of inventing."""
    rows = await session.execute(
        text(
            "SELECT label FROM (SELECT unnest(labels) AS label FROM tickets "
            "WHERE project_id = :project_id) AS used GROUP BY label "
            "ORDER BY count(*) DESC, label LIMIT 40"
        ),
        {"project_id": project_id},
    )
    return [row.label for row in rows]


async def _images(session: AsyncSession, storage: Storage, ticket_id: uuid.UUID) -> list[Image]:
    attachments = await session.scalars(
        select(TicketAttachment)
        .where(
            TicketAttachment.ticket_id == ticket_id,
            TicketAttachment.content_type.in_(list(_IMAGE_TYPES)),
            TicketAttachment.size_bytes <= MAX_IMAGE_BYTES,
        )
        .order_by(TicketAttachment.created_at)
        .limit(MAX_IMAGES)
    )
    images: list[Image] = []
    for attachment in attachments:
        data = await storage.get(attachment.storage_key)
        images.append(Image(data=data, media_type=_IMAGE_TYPES[attachment.content_type]))
    return images


async def _managed_run(
    session: AsyncSession, run_id: uuid.UUID, actor: User, *allowed: TriageStatus
) -> TriageRun:
    triage_run = await session.get(TriageRun, run_id)
    if triage_run is None:
        raise NotFoundError("Triage run not found")
    try:
        ticket = await get_ticket(session, triage_run.ticket_id, actor)
    except NotFoundError as exc:
        raise NotFoundError("Triage run not found") from exc
    await access.require_manager(session, ticket.project_id, actor)
    if triage_run.status not in allowed:
        raise ConflictError(f"This triage is {triage_run.status.value.replace('_', ' ')}")
    return triage_run


async def _fail(session: AsyncSession, triage_run: TriageRun, code: str) -> None:
    triage_run.status = TriageStatus.FAILED
    triage_run.error_code = code
    triage_run.finished_at = datetime.now(UTC)
    await session.commit()
    logger.warning("triage.failed", extra=log_fields(triage_run_id=triage_run.id, error=code))


async def _triage_dropping_bad_images(
    client: LLMClient, data: TriageInput, budget: RunBudget, run_id: uuid.UUID
) -> StructuredResult[TriageProposal]:
    """An attachment that looks like an image but isn't (corrupt, truncated) makes Claude reject
    the whole request. The ticket's text is still worth triaging: try once without images."""
    try:
        return await triage(client, data, budget)
    except LLMRequestRejectedError:
        if not data.images:
            raise
        logger.warning(
            "triage.images_dropped", extra=log_fields(triage_run_id=run_id, images=len(data.images))
        )
        return await triage(client, replace(data, images=[]), budget)


def _error_code(exc: Exception) -> str:
    """A short code the manager sees. Never the exception text: it could echo ticket content."""
    if isinstance(exc, LLMRefusalError):
        return "refused"
    if isinstance(exc, BudgetExceededError):
        return "over_budget"
    if isinstance(exc, LLMRequestRejectedError):
        return "rejected"
    if isinstance(exc, StorageError):
        return "storage_unavailable"
    return "ai_unavailable"
