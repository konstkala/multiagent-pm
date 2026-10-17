"""CV → profile draft. One structured Haiku call; a manager reviews the result before saving."""

from dataclasses import replace
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.llm import LLMClient, RunBudget, StructuredResult, Tier
from app.core.llm.content import pdf_block, text_block

PROMPT = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")
MAX_SKILLS = 25
MAX_TOKENS = 4_000  # ~25 skills with evidence fit in well under 2K; the rest is headroom


class SkillDraft(BaseModel):
    name: str = Field(description="Skill as usually written, e.g. 'PostgreSQL'")
    level: int = Field(description="1 mentioned, 2 basic, 3 working, 4 strong, 5 expert")
    evidence: str = Field(description="Why, in at most 20 words, from the CV")


class ProfileDraft(BaseModel):
    """Bounds are enforced in `clean`, not the schema: a slightly off answer is fixed, not lost."""

    headline: str
    summary: str
    years_experience: int | None
    skills: list[SkillDraft]


async def extract_profile(
    llm: LLMClient, pdf: bytes, budget: RunBudget
) -> StructuredResult[ProfileDraft]:
    # The CV (untrusted) goes in the user turn; the fixed instructions are the cached system prompt.
    content = [pdf_block(pdf), text_block("Build the profile from the CV above.")]
    result = await llm.complete_structured(
        tier=Tier.WORKER,
        # Extraction, not deep reasoning. Not yet measured: raise only if an eval shows gaps.
        effort="low",
        system=PROMPT,
        content=content,
        output_type=ProfileDraft,
        max_tokens=MAX_TOKENS,
        budget=budget,
    )
    return replace(result, output=clean(result.output))


def clean(draft: ProfileDraft) -> ProfileDraft:
    """Bring the model's answer inside our limits: lengths, levels, duplicates, count."""
    skills: dict[str, SkillDraft] = {}
    for skill in draft.skills:
        name = " ".join(skill.name.split())[:60]
        key = name.lower()
        if not name or key in skills:
            continue
        skills[key] = SkillDraft(
            name=name, level=min(5, max(1, skill.level)), evidence=skill.evidence.strip()[:200]
        )
        if len(skills) == MAX_SKILLS:
            break
    years = draft.years_experience
    return ProfileDraft(
        headline=" ".join(draft.headline.split())[:150],
        summary=draft.summary.strip()[:2000],
        years_experience=None if years is None or not 0 <= years <= 60 else years,
        skills=list(skills.values()),
    )
