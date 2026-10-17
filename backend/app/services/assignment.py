"""Assignee suggestions (ADR 0013, 0017): code ranks the project's members, the agent explains,
the manager picks by assigning as usual."""

import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.assignment import scoring
from app.agents.assignment.agent import LETTERS, AssignmentInput, CandidateFacts, explain
from app.core.errors import ConflictError
from app.core.llm import BudgetExceededError, LLMClient, LLMError, LLMRefusalError, RunBudget
from app.core.logging import log_fields
from app.db.models import (
    AssignmentRun,
    AssignmentStatus,
    EmployeeProfile,
    ProfileSkill,
    Project,
    ProjectMember,
    Ticket,
    TicketStatus,
    User,
)
from app.schemas.assignment import Candidate, ScoreParts, SkillFact
from app.schemas.assignment import CandidateFacts as FactsRead
from app.services import access, jobs
from app.services.embeddings import Embedder
from app.services.tickets import get_ticket

logger = logging.getLogger(__name__)

JOB_KIND = "assignment_reasons"
MAX_ATTEMPTS = 3
SIMILAR_DONE_MIN = 0.7
STRONGEST = 3
_OPEN = (TicketStatus.TODO, TicketStatus.IN_PROGRESS, TicketStatus.IN_REVIEW)


async def latest(session: AsyncSession, ticket_id: uuid.UUID, actor: User) -> AssignmentRun | None:
    # Managers only: suggestions reveal other people's workload and skills.
    ticket = await get_ticket(session, ticket_id, actor)
    await access.require_manager(session, ticket.project_id, actor)
    return await session.scalar(
        select(AssignmentRun)
        .where(AssignmentRun.ticket_id == ticket_id)
        .order_by(AssignmentRun.created_at.desc())
        .limit(1)
    )


async def suggest(
    session: AsyncSession, ticket_id: uuid.UUID, actor: User, embedder: Embedder
) -> AssignmentRun:
    """Ranks now (milliseconds) and queues the reasons, so the manager sees names at once."""
    ticket = await get_ticket(session, ticket_id, actor)
    await access.require_manager(session, ticket.project_id, actor)
    busy = await session.scalar(
        select(AssignmentRun.id).where(
            AssignmentRun.ticket_id == ticket_id,
            AssignmentRun.status == AssignmentStatus.EXPLAINING,
        )
    )
    if busy is not None:
        raise ConflictError("Suggestions for this ticket are still being written")
    project = await access.get_project(session, ticket.project_id, actor)

    started = time.perf_counter()
    people = await _people(session, ticket, project, embedder)
    history_available = await _history_available(session, ticket)
    ranking = scoring.rank(people, ticket.labels, history_available=history_available)
    score_ms = round((time.perf_counter() - started) * 1000, 1)

    run = AssignmentRun(
        ticket_id=ticket.id,
        requested_by=actor.id,
        candidates=[c.model_dump(mode="json") for c in _candidates(ranking)],
        score_ms=score_ms,
    )
    session.add(run)
    await session.flush()
    jobs.enqueue(session, JOB_KIND, {"run_id": str(run.id)}, priority=jobs.INTERACTIVE)
    await session.commit()
    logger.info(
        "audit.assignment.requested",
        extra=log_fields(actor=actor.id, assignment_run_id=run.id, ticket_id=ticket.id),
    )
    logger.info(
        "assignment.scored",
        extra=log_fields(
            assignment_run_id=run.id,
            team_size=len(people),
            candidates=len(ranking.candidates),
            history_available=history_available,
            score_ms=score_ms,
        ),
    )
    return run


async def run(
    session: AsyncSession, payload: dict[str, Any], *, llm: Callable[[], LLMClient]
) -> None:
    """The job: writes the reasons. Safe to run twice; a failure keeps the ranking usable."""
    assignment = await session.get(AssignmentRun, uuid.UUID(str(payload["run_id"])))
    if assignment is None or assignment.status is not AssignmentStatus.EXPLAINING:
        return
    ticket = await session.get(Ticket, assignment.ticket_id)
    project = await session.get(Project, ticket.project_id) if ticket else None
    if ticket is None or project is None:
        await _fail(session, assignment, "ticket_missing")
        return
    assignment.attempts += 1
    await session.commit()

    candidates = [Candidate.model_validate(c) for c in assignment.candidates]
    data = AssignmentInput(
        key=f"{project.key}-{ticket.number}",
        title=ticket.title,
        category=ticket.category.value if ticket.category else None,
        labels=ticket.labels,
        candidates=[
            _agent_facts(letter, c) for letter, c in zip(LETTERS, candidates, strict=False)
        ],
    )
    try:
        result = await explain(llm(), data, RunBudget(run_id=str(assignment.id)))
    except (LLMRefusalError, BudgetExceededError) as exc:
        await _fail(session, assignment, _error_code(exc))  # retrying won't help
        return
    except LLMError as exc:
        if assignment.attempts >= MAX_ATTEMPTS:
            await _fail(session, assignment, _error_code(exc))
            return
        raise  # the queue retries with backoff

    reasons = {r.candidate: r.reason for r in result.output.reasons}
    assignment.candidates = [
        c.model_copy(update={"reason": reasons.get(letter)}).model_dump(mode="json")
        for letter, c in zip(LETTERS, candidates, strict=False)
    ]
    assignment.model = result.model
    assignment.llm_calls += 1
    assignment.cost_usd += result.cost_usd
    assignment.latency_ms += result.latency_ms
    assignment.status = AssignmentStatus.READY
    assignment.finished_at = datetime.now(UTC)
    await session.commit()
    logger.info(
        "assignment.explained",
        extra=log_fields(
            assignment_run_id=assignment.id,
            cost_usd=round(assignment.cost_usd, 6),
            latency_ms=assignment.latency_ms,
        ),
    )


async def _people(
    session: AsyncSession, ticket: Ticket, project: Project, embedder: Embedder
) -> list[scoring.Person]:
    members = (
        await session.execute(
            select(User.id, User.display_name)
            .join(ProjectMember, ProjectMember.user_id == User.id)
            .where(ProjectMember.project_id == project.id)
        )
    ).all()
    ids = [member.id for member in members]
    profiles = {
        p.user_id: p
        for p in await session.scalars(
            select(EmployeeProfile).where(
                EmployeeProfile.workspace_id == project.workspace_id,
                EmployeeProfile.user_id.in_(ids),
            )
        )
    }
    skills: dict[uuid.UUID, list[scoring.Skill]] = defaultdict(list)
    for skill in await session.scalars(
        select(ProfileSkill).where(
            ProfileSkill.workspace_id == project.workspace_id, ProfileSkill.user_id.in_(ids)
        )
    ):
        skills[skill.user_id].append(scoring.Skill(name=skill.name, level=skill.level))
    filled = {
        user_id for user_id, p in profiles.items() if p.headline or p.summary or skills[user_id]
    }
    await _embed_profiles(session, [profiles[u] for u in filled], skills, embedder)
    similarity = await _profile_similarity(session, ticket, project.workspace_id, ids)
    similar_done = await _similar_done(session, ticket, ids)
    workload = await _workload(session, ticket, project.workspace_id, ids)
    return [
        scoring.Person(
            user_id=member.id,
            name=member.display_name,
            has_profile=member.id in filled,
            skills=skills[member.id],
            profile_similarity=similarity.get(member.id),
            similar_done=similar_done.get(member.id, 0),
            open_points=workload.get(member.id, (0, 0))[0],
            overdue=workload.get(member.id, (0, 0))[1],
        )
        for member in members
    ]


async def _embed_profiles(
    session: AsyncSession,
    profiles: list[EmployeeProfile],
    skills: dict[uuid.UUID, list[scoring.Skill]],
    embedder: Embedder,
) -> None:
    """Embeds profiles saved since their last use. Best effort: without it, labels still match."""
    stale = [p for p in profiles if p.embedding is None or p.embedding_model != embedder.model_name]
    if not stale:
        return
    texts = [
        f"{p.headline}\n{p.summary}\nSkills: {', '.join(s.name for s in skills[p.user_id])}"
        for p in stale
    ]
    try:
        vectors = await embedder.embed(texts)
    except Exception:  # model files missing, out of memory...
        logger.exception(
            "embeddings.failed", extra=log_fields(profiles=len(stale), model=embedder.model_name)
        )
        return
    for profile, vector in zip(stale, vectors, strict=True):
        profile.embedding = vector
        profile.embedding_model = embedder.model_name
    await session.flush()
    logger.info("embeddings.embedded", extra=log_fields(profiles=len(stale)))


async def _profile_similarity(
    session: AsyncSession, ticket: Ticket, workspace_id: uuid.UUID, ids: list[uuid.UUID]
) -> dict[uuid.UUID, float]:
    if ticket.embedding is None:
        return {}
    similarity = 1 - EmployeeProfile.embedding.cosine_distance(ticket.embedding)
    rows = await session.execute(
        select(EmployeeProfile.user_id, similarity).where(
            EmployeeProfile.workspace_id == workspace_id,
            EmployeeProfile.user_id.in_(ids),
            EmployeeProfile.embedding_model == ticket.embedding_model,
        )
    )
    return {user_id: float(value) for user_id, value in rows}


async def _similar_done(
    session: AsyncSession, ticket: Ticket, ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Who finished work like this before, in this project."""
    if ticket.embedding is None:
        return {}
    distance = Ticket.embedding.cosine_distance(ticket.embedding)
    rows = await session.execute(
        select(Ticket.assignee_id, func.count())
        .where(
            Ticket.project_id == ticket.project_id,
            Ticket.id != ticket.id,
            Ticket.status == TicketStatus.DONE,
            Ticket.assignee_id.in_(ids),
            Ticket.embedding_model == ticket.embedding_model,
            distance <= 1 - SIMILAR_DONE_MIN,
        )
        .group_by(Ticket.assignee_id)
    )
    return {user_id: count for user_id, count in rows if user_id is not None}


async def _history_available(session: AsyncSession, ticket: Ticket) -> bool:
    """Whether the project has any finished, assigned work to learn from yet."""
    done = exists().where(
        Ticket.project_id == ticket.project_id,
        Ticket.id != ticket.id,
        Ticket.status == TicketStatus.DONE,
        Ticket.assignee_id.is_not(None),
        Ticket.embedding.is_not(None),
    )
    return bool(await session.scalar(select(done)))


async def _workload(
    session: AsyncSession, ticket: Ticket, workspace_id: uuid.UUID, ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, int]]:
    """Open points and overdue tickets per person across the workspace: people work on several
    projects. This ticket itself doesn't count, so re-assigning compares fairly."""
    today = datetime.now(UTC).date()
    points = func.sum(func.coalesce(Ticket.story_points, scoring.UNPOINTED))
    overdue = func.count().filter(Ticket.due_date < today)
    rows = await session.execute(
        select(Ticket.assignee_id, points, overdue)
        .join(Project, Project.id == Ticket.project_id)
        .where(
            Project.workspace_id == workspace_id,
            Ticket.id != ticket.id,
            Ticket.assignee_id.in_(ids),
            Ticket.status.in_(_OPEN),
        )
        .group_by(Ticket.assignee_id)
    )
    return {user_id: (int(p), int(o)) for user_id, p, o in rows if user_id is not None}


def _candidates(ranking: scoring.Ranking) -> list[Candidate]:
    def skill_facts(found: list[scoring.Skill]) -> list[SkillFact]:
        return [SkillFact(name=s.name, level=s.level) for s in found]

    return [
        Candidate(
            user_id=s.person.user_id,
            display_name=s.person.name,
            rank=rank,
            score=round(s.score, 4),
            parts=ScoreParts(
                skill=round(s.skill, 4),
                history=round(s.history, 4),
                availability=round(s.availability, 4),
            ),
            facts=FactsRead(
                has_profile=s.person.has_profile,
                matched_skills=skill_facts(s.matched_skills),
                strongest_skills=skill_facts(
                    sorted(s.person.skills, key=lambda k: (-k.level, k.name))[:STRONGEST]
                ),
                profile_match=(
                    round(s.person.profile_similarity, 3)
                    if s.person.profile_similarity is not None
                    else None
                ),
                similar_done=s.person.similar_done,
                open_points=s.person.open_points,
                team_avg_points=round(ranking.team_avg_points, 1),
                overdue=s.person.overdue,
            ),
            reason=None,
        )
        for rank, s in enumerate(ranking.candidates, start=1)
    ]


def _agent_facts(letter: str, candidate: Candidate) -> CandidateFacts:
    facts = candidate.facts

    def skills(found: list[SkillFact]) -> list[scoring.Skill]:
        return [scoring.Skill(name=s.name, level=s.level) for s in found]

    return CandidateFacts(
        letter=letter,
        has_profile=facts.has_profile,
        matched_skills=skills(facts.matched_skills),
        strongest_skills=skills(facts.strongest_skills),
        profile_match=facts.profile_match,
        similar_done=facts.similar_done,
        open_points=facts.open_points,
        team_avg_points=facts.team_avg_points,
        overdue=facts.overdue,
    )


async def _fail(session: AsyncSession, assignment: AssignmentRun, code: str) -> None:
    assignment.status = AssignmentStatus.EXPLAIN_FAILED
    assignment.error_code = code
    assignment.finished_at = datetime.now(UTC)
    await session.commit()
    logger.warning(
        "assignment.explain_failed", extra=log_fields(assignment_run_id=assignment.id, error=code)
    )


def _error_code(exc: Exception) -> str:
    """A short code the manager sees. Never the exception text."""
    if isinstance(exc, LLMRefusalError):
        return "refused"
    if isinstance(exc, BudgetExceededError):
        return "over_budget"
    return "ai_unavailable"
