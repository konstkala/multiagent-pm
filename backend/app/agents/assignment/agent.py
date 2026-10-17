"""Ranked candidates → one sentence each on why. Code ranked them; this call only explains."""

from dataclasses import dataclass, replace
from pathlib import Path

from pydantic import BaseModel

from app.agents.assignment.scoring import Skill
from app.core.llm import LLMClient, RunBudget, StructuredResult, Tier, UserContent
from app.core.llm.content import tag, text_block

PROMPT = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")
LETTERS = ("A", "B", "C")
MAX_TOKENS = 600
MAX_REASON = 200


@dataclass(frozen=True)
class CandidateFacts:
    """What the model sees about a person: facts only. No name, email or profile text."""

    letter: str
    has_profile: bool
    matched_skills: list[Skill]
    strongest_skills: list[Skill]
    profile_match: float | None
    similar_done: int
    open_points: int
    team_avg_points: float
    overdue: int


@dataclass(frozen=True)
class AssignmentInput:
    key: str
    title: str
    category: str | None
    labels: list[str]
    candidates: list[CandidateFacts]


class Reason(BaseModel):
    candidate: str
    reason: str


class AssignmentReasons(BaseModel):
    reasons: list[Reason]


async def explain(
    llm: LLMClient, data: AssignmentInput, budget: RunBudget
) -> StructuredResult[AssignmentReasons]:
    result = await llm.complete_structured(
        tier=Tier.WORKER,
        effort="low",  # rewording given facts; nothing to reason out
        system=PROMPT,
        content=build_content(data),
        output_type=AssignmentReasons,
        max_tokens=MAX_TOKENS,
        budget=budget,
    )
    return replace(result, output=clean(result.output, data))


def build_content(data: AssignmentInput) -> list[UserContent]:
    ticket = (
        f"key: {data.key}\ntitle: {data.title}\ncategory: {data.category or 'not set'}\n"
        f"labels: {', '.join(data.labels) or 'none'}"
    )
    candidates = "\n".join(_facts_line(c) for c in data.candidates)
    return [text_block(f"{tag('ticket', ticket)}\n\n{tag('candidates', candidates)}")]


def clean(output: AssignmentReasons, data: AssignmentInput) -> AssignmentReasons:
    """One reason per candidate, in ranking order. A missing one is written from the facts."""
    given = {r.candidate.strip().upper(): " ".join(r.reason.split()) for r in output.reasons}
    return AssignmentReasons(
        reasons=[
            Reason(
                candidate=c.letter,
                reason=(given.get(c.letter) or fallback_reason(c))[:MAX_REASON],
            )
            for c in data.candidates
        ]
    )


def fallback_reason(c: CandidateFacts) -> str:
    parts: list[str] = []
    if c.matched_skills:
        parts.append("Knows " + ", ".join(f"{s.name} ({s.level}/5)" for s in c.matched_skills))
    elif not c.has_profile:
        parts.append("No profile yet")
    if c.similar_done:
        parts.append(f"{c.similar_done} similar done")
    parts.append(f"{c.open_points} open points (team average {c.team_avg_points:.0f})")
    if c.overdue:
        parts.append(f"{c.overdue} overdue")
    return "; ".join(parts) + "."


def _facts_line(c: CandidateFacts) -> str:
    def skills(found: list[Skill]) -> str:
        return ", ".join(f"{s.name} {s.level}/5" for s in found) or "none"

    match = f"{c.profile_match:.2f}" if c.profile_match is not None else "unknown"
    profile = (
        f"matched skills: {skills(c.matched_skills)} | strongest skills: "
        f"{skills(c.strongest_skills)} | profile match: {match}"
        if c.has_profile
        else "no profile yet"
    )
    return (
        f"{c.letter} | {profile} | similar done: {c.similar_done} | open points: "
        f"{c.open_points} (team average {c.team_avg_points:.1f}) | overdue: {c.overdue}"
    )
