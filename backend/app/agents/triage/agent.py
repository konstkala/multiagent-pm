"""Ticket → triage proposal. One structured Haiku call; a manager reviews what isn't applied."""

import uuid
from dataclasses import dataclass, replace
from pathlib import Path

from pydantic import BaseModel

from app.core.llm import LLMClient, RunBudget, StructuredResult, Tier, UserContent
from app.core.llm.content import ImageType, image_block, text_block
from app.db.models import TicketCategory, TicketPriority

PROMPT = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")
FIBONACCI = (1, 2, 3, 5, 8, 13)
MAX_LABELS = 5
MAX_TOKENS = 2_000


@dataclass(frozen=True)
class SimilarTicket:
    id: uuid.UUID
    number: int
    title: str
    status: str
    category: str | None
    story_points: int | None
    similarity: float


@dataclass(frozen=True)
class Image:
    data: bytes
    media_type: ImageType


@dataclass(frozen=True)
class TriageInput:
    key: str
    title: str
    description: str
    similar: list[SimilarTicket]
    project_labels: list[str]
    images: list[Image]
    question: str | None = None
    answer: str | None = None


class TriageProposal(BaseModel):
    """Bounds are enforced in `clean`, not the schema: a slightly off answer is fixed, not lost."""

    category: TicketCategory
    labels: list[str]
    priority: TicketPriority
    story_points: int
    duplicate_of: int | None
    classification_confidence: float
    sizing_confidence: float
    reason: str
    question: str | None


async def triage(
    llm: LLMClient, data: TriageInput, budget: RunBudget
) -> StructuredResult[TriageProposal]:
    result = await llm.complete_structured(
        tier=Tier.WORKER,
        # Classification and comparison, not deep reasoning. Raise only if an eval shows gaps.
        effort="low",
        system=PROMPT,
        content=build_content(data),
        output_type=TriageProposal,
        max_tokens=MAX_TOKENS,
        budget=budget,
    )
    return replace(result, output=clean(result.output, data))


def build_content(data: TriageInput) -> list[UserContent]:
    """Images first, then the text that refers to them. All of it is untrusted data."""
    parts = [
        _tag("ticket", f"key: {data.key}\ntitle: {data.title}\ndescription:\n{data.description}"),
        _tag(
            "similar_tickets",
            "\n".join(
                f"#{t.number} | {t.title} | status {t.status} | category {t.category or '-'} "
                f"| points {t.story_points or '-'} | similarity {t.similarity:.2f}"
                for t in data.similar
            )
            or "none",
        ),
        _tag("project_labels", ", ".join(data.project_labels) or "none yet"),
    ]
    if data.answer is not None:
        parts.append(_tag("manager_answer", f"You asked: {data.question}\nAnswer: {data.answer}"))
    return [
        *(image_block(image.data, image.media_type) for image in data.images),
        text_block("\n\n".join(parts)),
    ]


def clean(proposal: TriageProposal, data: TriageInput) -> TriageProposal:
    """Bring the answer inside our rules: label format, real story points, real candidates."""
    labels: list[str] = []
    for label in proposal.labels:
        normal = " ".join(label.lower().split())[:50]
        if normal and normal not in labels:
            labels.append(normal)
    candidates = {t.number for t in data.similar}
    question = (proposal.question or "").strip()[:300]
    return proposal.model_copy(
        update={
            "labels": labels[:MAX_LABELS],
            "story_points": nearest_fibonacci(proposal.story_points),
            "duplicate_of": proposal.duplicate_of if proposal.duplicate_of in candidates else None,
            "classification_confidence": _unit(proposal.classification_confidence),
            "sizing_confidence": _unit(proposal.sizing_confidence),
            "reason": proposal.reason.strip()[:300],
            # One question at most: after an answer, the agent must decide.
            "question": question if question and data.answer is None else None,
        }
    )


def _tag(name: str, body: str) -> str:
    # Stops ticket text from closing our tag and posing as instructions.
    return f"<{name}>\n{body.replace('</', '< /')}\n</{name}>"


def nearest_fibonacci(points: int) -> int:
    # Ties go up: when unsure, assume more effort, not less.
    return min(FIBONACCI, key=lambda p: (abs(p - points), -p))


def _unit(value: float) -> float:
    return min(1.0, max(0.0, value))
