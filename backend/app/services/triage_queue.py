"""Queue a triage run. Separate from services/triage.py so the ticket service can call it."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Ticket, TriageRun, TriageTrigger
from app.services import jobs

JOB_KIND = "triage"


async def enqueue(
    session: AsyncSession, ticket: Ticket, trigger: TriageTrigger
) -> TriageRun | None:
    """Adds the run and its job to the caller's transaction."""
    if not settings.triage_enabled:
        return None
    run = TriageRun(ticket_id=ticket.id, trigger=trigger)
    session.add(run)
    await session.flush()
    jobs.enqueue(session, JOB_KIND, {"run_id": str(run.id)})
    return run
