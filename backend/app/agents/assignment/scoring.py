"""Who fits a ticket best: plain code, $0, testable (ADR 0013). The LLM only explains the result."""

import uuid
from dataclasses import dataclass

TOP = 3
WEIGHTS = {"skill": 0.45, "history": 0.35, "availability": 0.20}
SEMANTIC_SHARE = 0.7  # of skill fit; the rest is ticket labels matching named skills
# bge-small puts unrelated texts around 0.5 and close ones near 0.9: stretch that range to 0..1.
SIMILARITY_FLOOR = 0.5
SIMILARITY_SPAN = 0.4
SIMILAR_DONE_CAP = 3  # caps the "rich get richer" pull of past work
OVERDUE_PENALTY = 0.15
UNPOINTED = 3  # an open ticket nobody sized still takes time


@dataclass(frozen=True)
class Skill:
    name: str
    level: int  # 1 beginner ... 5 expert


@dataclass(frozen=True)
class Person:
    user_id: uuid.UUID
    name: str  # only to break ties; never sent to the model
    has_profile: bool
    skills: list[Skill]
    # Cosine similarity of ticket and profile; None when either has no embedding.
    profile_similarity: float | None
    similar_done: int  # finished tickets in this project close to this one
    open_points: int
    overdue: int


@dataclass(frozen=True)
class Scored:
    person: Person
    score: float
    skill: float
    history: float
    availability: float
    matched_skills: list[Skill]


@dataclass(frozen=True)
class Ranking:
    team_avg_points: float
    candidates: list[Scored]


def rank(people: list[Person], labels: list[str], *, history_available: bool) -> Ranking:
    """The top 3. With no finished work in the project yet, history's weight moves to the rest."""
    team_avg = sum(p.open_points for p in people) / len(people) if people else 0.0
    weights = _weights(history_available)
    scored = [_score(person, labels, team_avg, weights) for person in people]
    # Rounded so near-equal scores fall through to the fairer tie-break: less work first.
    scored.sort(key=lambda s: (-round(s.score, 4), s.person.open_points, s.person.name.lower()))
    return Ranking(team_avg_points=team_avg, candidates=scored[:TOP])


def matched_skills(skills: list[Skill], labels: list[str]) -> list[Skill]:
    wanted = {label.lower() for label in labels}
    return sorted((s for s in skills if s.name.lower() in wanted), key=lambda s: -s.level)


def skill_fit(person: Person, matched: list[Skill]) -> float:
    if not person.has_profile:
        return 0.0
    label_match = max((s.level for s in matched), default=0) / 5
    if person.profile_similarity is None:
        return label_match
    semantic = _unit((person.profile_similarity - SIMILARITY_FLOOR) / SIMILARITY_SPAN)
    return SEMANTIC_SHARE * semantic + (1 - SEMANTIC_SHARE) * label_match


def history(person: Person) -> float:
    return min(person.similar_done, SIMILAR_DONE_CAP) / SIMILAR_DONE_CAP


def availability(person: Person, team_avg: float) -> float:
    """1 with nothing open, 0.5 at the team average, lower with overdue work."""
    free = 1 / (1 + person.open_points / max(team_avg, 1.0))
    return _unit(free - OVERDUE_PENALTY * person.overdue)


def _score(person: Person, labels: list[str], team_avg: float, weights: dict[str, float]) -> Scored:
    matched = matched_skills(person.skills, labels)
    parts = {
        "skill": skill_fit(person, matched),
        "history": history(person),
        "availability": availability(person, team_avg),
    }
    return Scored(
        person=person,
        score=sum(weights[name] * value for name, value in parts.items()),
        matched_skills=matched,
        **parts,
    )


def _weights(history_available: bool) -> dict[str, float]:
    if history_available:
        return WEIGHTS
    rest = WEIGHTS["skill"] + WEIGHTS["availability"]
    return {
        "skill": WEIGHTS["skill"] / rest,
        "history": 0.0,
        "availability": WEIGHTS["availability"] / rest,
    }


def _unit(value: float) -> float:
    return min(1.0, max(0.0, value))
