"""Records who a manager actually assigned after asking for suggestions: the agent's hit rate.
Separate from services/assignment.py so the ticket service can call it."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import log_fields
from app.db.models import AssignmentRun, User

logger = logging.getLogger(__name__)


async def record_choice(
    session: AsyncSession, ticket_id: uuid.UUID, assignee_id: uuid.UUID, actor: User
) -> None:
    """Marks the latest undecided suggestion run, in the caller's transaction. Any way of
    assigning counts (the suggestion's button or the plain select), so the rate stays honest."""
    run = await session.scalar(
        select(AssignmentRun)
        .where(AssignmentRun.ticket_id == ticket_id, AssignmentRun.decided_at.is_(None))
        .order_by(AssignmentRun.created_at.desc())
        .limit(1)
    )
    if run is None:
        return
    run.chosen_user_id = assignee_id
    run.chosen_rank = next(
        (c["rank"] for c in run.candidates if c["user_id"] == str(assignee_id)), None
    )
    run.decided_at = datetime.now(UTC)
    logger.info(
        "audit.assignment.chosen",
        extra=log_fields(
            actor=actor.id,
            assignment_run_id=run.id,
            ticket_id=ticket_id,
            chosen_rank=run.chosen_rank,
        ),
    )
