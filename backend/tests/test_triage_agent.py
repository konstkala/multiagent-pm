import uuid

import pytest

from app.agents.triage.agent import (
    SimilarTicket,
    TriageInput,
    TriageProposal,
    clean,
    nearest_fibonacci,
    triage,
)
from app.core.llm import RunBudget, create_llm_client
from app.db.models import TicketCategory, TicketPriority

EMPTY = TriageInput(
    key="PM-9", title="t", description="d", similar=[], project_labels=[], images=[]
)


@pytest.mark.parametrize(
    ("given", "expected"), [(0, 1), (4, 5), (6, 5), (7, 8), (10, 8), (11, 13), (40, 13)]
)
def test_story_points_snap_to_the_scale_and_ties_go_up(given: int, expected: int) -> None:
    assert nearest_fibonacci(given) == expected


def test_clean_normalises_labels_and_confidence() -> None:
    raw = TriageProposal(
        category=TicketCategory.BUG,
        labels=["  Back  End ", "back end", "db", "a", "b", "c", "d"],
        priority=TicketPriority.LOW,
        story_points=3,
        duplicate_of=None,
        classification_confidence=1.7,
        sizing_confidence=-0.2,
        reason=" ok ",
        question="  ",
    )

    cleaned = clean(raw, EMPTY)

    assert cleaned.labels == ["back end", "db", "a", "b", "c"]
    assert (cleaned.classification_confidence, cleaned.sizing_confidence) == (1.0, 0.0)
    assert cleaned.question is None


@pytest.mark.llm
async def test_live_triage_of_a_real_ticket() -> None:
    """One real Haiku call, well under $0.01. Run with: uv run pytest -m llm"""
    data = TriageInput(
        key="PM-12",
        title="Checkout fails with 500 when the cart has a discount code",
        description=(
            "Customers can't pay. Since this morning's deploy. Error in payment service logs."
        ),
        similar=[
            SimilarTicket(
                id=uuid.uuid4(),
                number=7,
                title="Payment service returns 500 for discounted carts",
                status="todo",
                category="bug",
                story_points=3,
                similarity=0.84,
            )
        ],
        project_labels=["payments", "backend", "frontend"],
        images=[],
    )

    result = await triage(create_llm_client(), data, RunBudget("live-triage"))
    proposal = result.output

    assert proposal.category is TicketCategory.BUG
    assert proposal.priority in (TicketPriority.URGENT, TicketPriority.HIGH)
    assert "payments" in proposal.labels
    assert proposal.story_points in (1, 2, 3, 5, 8, 13)
    assert result.cost_usd < 0.01
