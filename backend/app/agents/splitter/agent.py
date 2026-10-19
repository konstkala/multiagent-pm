"""Ticket → sub-ticket split. Three structured calls (draft, critique, revise) that the graph in
`graph.py` strings together; a manager approves what is created."""

from dataclasses import dataclass, replace
from pathlib import Path

from pydantic import BaseModel

from app.agents.triage.agent import FIBONACCI, nearest_fibonacci
from app.core.llm import LLMClient, RunBudget, StructuredResult, Tier, UserContent
from app.core.llm.content import tag, text_block

DRAFT_PROMPT = (Path(__file__).parent / "prompt_draft.md").read_text(encoding="utf-8")
CRITIQUE_PROMPT = (Path(__file__).parent / "prompt_critique.md").read_text(encoding="utf-8")
MIN_POINTS = 8  # smaller tickets are not worth splitting
MAX_SUB_TICKETS = 5
MAX_ISSUES = 4
MAX_TOKENS = 1_500
CRITIQUE_MAX_TOKENS = 600


@dataclass(frozen=True)
class SplitInput:
    key: str
    title: str
    description: str
    story_points: int
    category: str | None


class SubTicketDraft(BaseModel):
    title: str
    description: str
    story_points: int


class SplitDraft(BaseModel):
    """Bounds are enforced in `clean`, not the schema: a slightly off answer is fixed, not lost."""

    sub_tickets: list[SubTicketDraft]
    reason: str


class Critique(BaseModel):
    ok: bool
    issues: list[str]


async def draft(
    llm: LLMClient, data: SplitInput, budget: RunBudget
) -> StructuredResult[SplitDraft]:
    result = await llm.complete_structured(
        tier=Tier.WORKER,
        effort="low",  # cutting work into pieces; the critic does the checking
        system=DRAFT_PROMPT,
        content=[text_block(_ticket_tag(data))],
        output_type=SplitDraft,
        max_tokens=MAX_TOKENS,
        budget=budget,
    )
    return replace(result, output=clean(result.output, data))


async def revise(
    llm: LLMClient, data: SplitInput, previous: SplitDraft, issues: list[str], budget: RunBudget
) -> StructuredResult[SplitDraft]:
    content: list[UserContent] = [
        text_block(
            f"{_ticket_tag(data)}\n\n{_proposal_tag('previous_draft', previous)}\n\n"
            f"{tag('critic_issues', chr(10).join(f'- {issue}' for issue in issues))}"
        )
    ]
    result = await llm.complete_structured(
        tier=Tier.WORKER,
        effort="low",
        system=DRAFT_PROMPT,  # same instructions as the draft: it already says how to revise
        content=content,
        output_type=SplitDraft,
        max_tokens=MAX_TOKENS,
        budget=budget,
    )
    return replace(result, output=clean(result.output, data))


async def critique(
    llm: LLMClient, data: SplitInput, proposal: SplitDraft, budget: RunBudget
) -> StructuredResult[Critique]:
    result = await llm.complete_structured(
        tier=Tier.ORCHESTRATOR,  # judging someone else's work is where the stronger model pays off
        effort="medium",
        system=CRITIQUE_PROMPT,
        content=[text_block(f"{_ticket_tag(data)}\n\n{_proposal_tag('proposal', proposal)}")],
        output_type=Critique,
        max_tokens=CRITIQUE_MAX_TOKENS,
        budget=budget,
    )
    issues = [" ".join(i.split())[:300] for i in result.output.issues if i.strip()]
    cleaned = Critique(ok=result.output.ok and not issues, issues=issues[:MAX_ISSUES])
    return replace(result, output=cleaned)


def clean(proposal: SplitDraft, data: SplitInput) -> SplitDraft:
    """Bring the answer inside our rules: at most 5 pieces, real story points, all smaller than
    the ticket. Whether the pieces make sense is the critic's and the manager's call."""
    sub_tickets = [
        SubTicketDraft(
            title=" ".join(s.title.split())[:200],
            description=s.description.strip()[:2_000],
            story_points=_smaller_than(s.story_points, data.story_points),
        )
        for s in proposal.sub_tickets
        if s.title.strip()
    ]
    return SplitDraft(
        sub_tickets=sub_tickets[:MAX_SUB_TICKETS], reason=proposal.reason.strip()[:300]
    )


def _smaller_than(points: int, parent: int) -> int:
    snapped = nearest_fibonacci(points)
    if snapped < parent:
        return snapped
    return max(p for p in FIBONACCI if p < parent)


def _ticket_tag(data: SplitInput) -> str:
    return tag(
        "ticket",
        f"key: {data.key}\ntitle: {data.title}\ncategory: {data.category or 'not set'}\n"
        f"story_points: {data.story_points}\ndescription:\n{data.description}",
    )


def _proposal_tag(name: str, proposal: SplitDraft) -> str:
    lines = [
        f"{number}. {s.title} ({s.story_points} pts)\n{s.description}"
        for number, s in enumerate(proposal.sub_tickets, start=1)
    ]
    return tag(name, "\n\n".join(lines) or "none")
