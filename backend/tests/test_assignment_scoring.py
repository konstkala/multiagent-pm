import uuid
from dataclasses import replace
from typing import Any

import pytest

from app.agents.assignment.scoring import (
    Person,
    Skill,
    availability,
    matched_skills,
    rank,
    skill_fit,
)


def person(name: str = "Ana", **overrides: Any) -> Person:
    base = Person(
        user_id=uuid.uuid4(),
        name=name,
        has_profile=True,
        skills=[],
        profile_similarity=None,
        similar_done=0,
        open_points=0,
        overdue=0,
    )
    return replace(base, **overrides)


def test_matched_skills_ignore_case_and_put_the_strongest_first() -> None:
    skills = [Skill("Payments", 3), Skill("react", 5), Skill("Backend", 4)]

    assert matched_skills(skills, ["backend", "PAYMENTS"]) == [
        Skill("Backend", 4),
        Skill("Payments", 3),
    ]


@pytest.mark.parametrize(
    ("similarity", "expected"),
    [(None, 0.8), (0.4, 0.24), (0.7, 0.59), (0.95, 0.94)],  # 0.3 * 4/5 label part + semantic
)
def test_skill_fit_mixes_profile_similarity_and_label_level(
    similarity: float | None, expected: float
) -> None:
    ana = person(skills=[Skill("payments", 4)], profile_similarity=similarity)

    assert skill_fit(ana, matched_skills(ana.skills, ["payments"])) == pytest.approx(expected)


def test_no_profile_means_no_skill_fit() -> None:
    assert skill_fit(person(has_profile=False, profile_similarity=0.9), []) == 0


@pytest.mark.parametrize(
    ("open_points", "overdue", "team_avg", "expected"),
    [
        (0, 0, 6, 1.0),
        (6, 0, 6, 0.5),
        (6, 2, 6, 0.2),
        (12, 0, 6, 1 / 3),
        (6, 4, 6, 0.0),
        (1, 0, 0, 0.5),
    ],
)
def test_availability_halves_at_the_team_average_and_drops_with_overdue_work(
    open_points: int, overdue: int, team_avg: float, expected: float
) -> None:
    busy = person(open_points=open_points, overdue=overdue)

    assert availability(busy, team_avg) == pytest.approx(expected)


def test_history_counts_only_when_the_project_has_some() -> None:
    expert = person("Ana", similar_done=3)
    # A weak profile match (0.4 counts as 0), so only the 5/5 label part: 0.3.
    newcomer = person("Ben", skills=[Skill("payments", 5)], profile_similarity=0.4)

    with_history = rank([expert, newcomer], ["payments"], history_available=True)
    cold_start = rank([expert, newcomer], ["payments"], history_available=False)

    assert [c.person.name for c in with_history.candidates] == ["Ana", "Ben"]
    assert [c.person.name for c in cold_start.candidates] == ["Ben", "Ana"]
    # History's 0.35 is spread over skill and availability, so the weights still add up to 1.
    assert cold_start.candidates[0].score == pytest.approx(0.45 / 0.65 * 0.3 + 0.20 / 0.65)


def test_ties_go_to_less_work_then_name_and_only_three_are_returned() -> None:
    people = [
        person("Dan", has_profile=False, open_points=0),
        person("cara", has_profile=False, open_points=0),
        person("Ben", has_profile=False, open_points=0),
        person("Ana", has_profile=False, open_points=0, overdue=0),
    ]

    ranking = rank(people, [], history_available=False)

    assert [c.person.name for c in ranking.candidates] == ["Ana", "Ben", "cara"]
    assert ranking.team_avg_points == 0
