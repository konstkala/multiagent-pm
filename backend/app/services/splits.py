"""Ticket splits (ADR 0021): the splitter graph proposes sub-tickets, a manager keeps some.

Two kinds of state: the `split_runs` row is what screens read; LangGraph's checkpoint (keyed by
the row's id) is what lets the graph resume where it paused. Only this module touches both."""

import logging
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.checkpoint import checkpointer
from app.agents.splitter.agent import MIN_POINTS, SplitInput
from app.agents.splitter.graph import build_graph, initial_state
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.llm import (
    BudgetExceededError,
    LLMClient,
    LLMError,
    LLMRefusalError,
    LLMRequestRejectedError,
    RunBudget,
)
from app.core.logging import log_fields
from app.db.models import Project, SplitRun, SplitStatus, Ticket, User
from app.schemas.tickets import TicketCreate
from app.services import access, jobs
from app.services.embeddings import Embedder
from app.services.tickets import add_ticket, get_ticket, log_ticket_created

logger = logging.getLogger(__name__)

JOB_KIND = "ticket_split"
MAX_ATTEMPTS = 3
_OPEN = (SplitStatus.QUEUED, SplitStatus.RUNNING, SplitStatus.PROPOSED, SplitStatus.RESUMING)


async def latest(session: AsyncSession, ticket_id: uuid.UUID, actor: User) -> SplitRun | None:
    ticket = await get_ticket(session, ticket_id, actor)
    await access.require_manager(session, ticket.project_id, actor)
    return await session.scalar(
        select(SplitRun)
        .where(SplitRun.ticket_id == ticket_id)
        .order_by(SplitRun.created_at.desc())
        .limit(1)
    )


async def request_split(session: AsyncSession, ticket_id: uuid.UUID, actor: User) -> SplitRun:
    ticket = await get_ticket(session, ticket_id, actor)
    await access.require_manager(session, ticket.project_id, actor)
    if ticket.parent_id is not None:
        raise ConflictError("A sub-task can't be split")
    if (ticket.story_points or 0) < MIN_POINTS:
        raise ConflictError(f"Only tickets of {MIN_POINTS} points or more can be split")
    open_run = await session.scalar(
        select(SplitRun.id).where(SplitRun.ticket_id == ticket_id, SplitRun.status.in_(_OPEN))
    )
    if open_run is not None:
        raise ConflictError("This ticket is already being split")
    run = SplitRun(ticket_id=ticket.id, requested_by=actor.id)
    session.add(run)
    await session.flush()
    jobs.enqueue(session, JOB_KIND, {"run_id": str(run.id)}, priority=jobs.INTERACTIVE)
    await session.commit()
    logger.info(
        "audit.split.requested",
        extra=log_fields(actor=actor.id, split_run_id=run.id, ticket_id=ticket.id),
    )
    return run


async def decide(
    session: AsyncSession, run_id: uuid.UUID, keep: list[int], actor: User
) -> SplitRun:
    """The manager's answer to the graph's interrupt. An empty list rejects the proposal."""
    run = await _managed_run(session, run_id, actor, SplitStatus.PROPOSED)
    count = len((run.proposal or {}).get("sub_tickets", []))
    if len(set(keep)) != len(keep) or any(not 0 <= index < count for index in keep):
        raise ConflictError("Pick each proposed sub-ticket at most once")
    run.accepted = sorted(keep)
    run.decided_by = actor.id
    run.decided_at = datetime.now(UTC)
    run.status = SplitStatus.RESUMING
    jobs.enqueue(session, JOB_KIND, {"run_id": str(run.id)}, priority=jobs.INTERACTIVE)
    await session.commit()
    logger.info(
        "audit.split.decided",
        extra=log_fields(actor=actor.id, split_run_id=run.id, kept=len(keep), proposed=count),
    )
    return run


async def run(
    session: AsyncSession,
    payload: dict[str, Any],
    *,
    llm: Callable[[], LLMClient],
    embedder: Embedder,
    checkpoints: Callable[[], AbstractAsyncContextManager[AsyncPostgresSaver]] = checkpointer,
) -> None:
    """The job. Starts the graph, continues it from its checkpoint after a crash, or resumes it
    with the manager's answer. Safe to run twice: finished runs are left alone."""
    split = await session.get(SplitRun, uuid.UUID(str(payload["run_id"])))
    if split is None or split.status not in (
        SplitStatus.QUEUED,
        SplitStatus.RUNNING,
        SplitStatus.RESUMING,
    ):
        return
    ticket = await session.get(Ticket, split.ticket_id)
    project = await session.get(Project, ticket.project_id) if ticket else None
    if ticket is None or project is None:
        await _fail(session, split, "ticket_missing")
        return
    split.attempts += 1
    if split.status is SplitStatus.QUEUED:
        split.status = SplitStatus.RUNNING
    await session.commit()

    budget = RunBudget(run_id=str(split.id))
    budget.record(split.cost_usd)  # a resume after the interrupt shares the cap
    try:
        async with checkpoints() as saver:
            graph = build_graph(llm(), budget, saver)
            config: Any = {"configurable": {"thread_id": str(split.id)}}
            snapshot = await graph.aget_state(config)
            interrupted = False
            if snapshot.values and not snapshot.next:
                graph_input = None  # finished before a crash; only the writes are left
            elif split.status is SplitStatus.RESUMING:
                graph_input = Command(resume=split.accepted or [])
            elif snapshot.values:
                graph_input = None  # a crash mid-run: carry on from the last checkpoint
            else:
                graph_input = initial_state(_input(ticket, project))
            if graph_input is not None or snapshot.next:
                updates = graph.astream(  # pyright: ignore[reportUnknownMemberType]
                    graph_input, config, stream_mode="updates"
                )
                async for update in updates:
                    for node, change in update.items():
                        if node == "__interrupt__":
                            interrupted = True
                        else:
                            await _record_node(session, split, node, change)
            state = (await graph.aget_state(config)).values
    except (LLMRefusalError, BudgetExceededError, LLMRequestRejectedError) as exc:
        await _fail(session, split, _error_code(exc))  # retrying won't help
        return
    except LLMError as exc:
        if split.attempts >= MAX_ATTEMPTS:
            await _fail(session, split, _error_code(exc))
            return
        raise  # the queue retries with backoff, and the graph continues from its checkpoint

    if interrupted:
        await _propose(session, split, state)
    else:
        await _finish(session, split, ticket, state.get("kept", []), embedder)


async def _record_node(
    session: AsyncSession, split: SplitRun, node: str, change: dict[str, Any]
) -> None:
    """Progress after every node, so the screen can say what the graph is doing."""
    calls: list[dict[str, Any]] = change.get("calls", [])
    split.step = node
    if "rounds" in change:
        split.rounds = change["rounds"]
    split.calls = [*split.calls, *calls]
    split.llm_calls += len(calls)
    split.cost_usd += sum(call["cost_usd"] for call in calls)
    split.latency_ms += sum(call["latency_ms"] for call in calls)
    await session.commit()
    logger.info(
        "split.node_finished",
        extra=log_fields(
            split_run_id=split.id,
            node=node,
            round=split.rounds,
            cost_usd=round(sum(call["cost_usd"] for call in calls), 6),
            latency_ms=round(sum(call["latency_ms"] for call in calls), 1),
        ),
    )


async def _propose(session: AsyncSession, split: SplitRun, state: dict[str, Any]) -> None:
    split.proposal = {**state["draft"], "issues": state["issues"], "rounds": state["rounds"]}
    split.status = SplitStatus.PROPOSED
    split.step = None
    await session.commit()
    logger.info(
        "split.proposed",
        extra=log_fields(
            split_run_id=split.id,
            sub_tickets=len(state["draft"]["sub_tickets"]),
            rounds=state["rounds"],
            llm_calls=split.llm_calls,
            cost_usd=round(split.cost_usd, 6),
        ),
    )


async def _finish(
    session: AsyncSession,
    split: SplitRun,
    ticket: Ticket,
    kept: list[int],
    embedder: Embedder,
) -> None:
    """Creates the chosen sub-tickets in one transaction, or records that none were wanted."""
    now = datetime.now(UTC)
    split.step = None
    split.finished_at = now
    if not kept:
        split.status = SplitStatus.DISMISSED
        await session.commit()
        logger.info("audit.split.dismissed", extra=log_fields(split_run_id=split.id))
        return
    manager = await session.get(User, split.decided_by) if split.decided_by else None
    project = await session.get(Project, ticket.project_id)
    if manager is None or project is None:
        await _fail(session, split, "decider_missing")
        return
    proposed: list[dict[str, Any]] = (split.proposal or {})["sub_tickets"]
    created: list[Ticket] = []
    try:
        for index in kept:
            sub = proposed[index]
            created.append(
                await add_ticket(
                    session,
                    ticket.project_id,
                    TicketCreate.model_validate(
                        {
                            "title": sub["title"],
                            "description": sub["description"],
                            "story_points": sub["story_points"],
                            "category": ticket.category,
                            "priority": ticket.priority,
                            "labels": ticket.labels,
                            "parent_id": ticket.id,
                        }
                    ),
                    manager,
                    embedder,
                )
            )
    except DomainError:  # e.g. the ticket became a sub-task while the manager was deciding
        await session.rollback()
        await _fail(session, split, "ticket_changed")
        return
    split.created_ticket_ids = [t.id for t in created]
    split.status = SplitStatus.APPLIED
    await session.commit()
    for child in created:
        log_ticket_created(child, manager, split_run_id=split.id, parent_id=ticket.id)
    logger.info(
        "audit.split.applied",
        extra=log_fields(
            actor=manager.id,
            split_run_id=split.id,
            ticket_id=ticket.id,
            created=len(created),
            cost_usd=round(split.cost_usd, 6),
        ),
    )


def _input(ticket: Ticket, project: Project) -> SplitInput:
    return SplitInput(
        key=f"{project.key}-{ticket.number}",
        title=ticket.title,
        description=ticket.description,
        story_points=ticket.story_points or MIN_POINTS,
        category=ticket.category.value if ticket.category else None,
    )


async def _managed_run(
    session: AsyncSession, run_id: uuid.UUID, actor: User, *allowed: SplitStatus
) -> SplitRun:
    split = await session.get(SplitRun, run_id)
    if split is None:
        raise NotFoundError("Split run not found")
    try:
        ticket = await get_ticket(session, split.ticket_id, actor)
    except NotFoundError as exc:
        raise NotFoundError("Split run not found") from exc
    await access.require_manager(session, ticket.project_id, actor)
    if split.status not in allowed:
        raise ConflictError(f"This split is {split.status.value}")
    return split


async def _fail(session: AsyncSession, split: SplitRun, code: str) -> None:
    split.status = SplitStatus.FAILED
    split.step = None
    split.error_code = code
    split.finished_at = datetime.now(UTC)
    await session.commit()
    logger.warning("split.failed", extra=log_fields(split_run_id=split.id, error=code))


def _error_code(exc: Exception) -> str:
    """A short code the manager sees. Never the exception text: it could echo ticket content."""
    if isinstance(exc, LLMRefusalError):
        return "refused"
    if isinstance(exc, BudgetExceededError):
        return "over_budget"
    if isinstance(exc, LLMRequestRejectedError):
        return "rejected"
    return "ai_unavailable"
