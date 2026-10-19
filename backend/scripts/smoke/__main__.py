"""Runs every milestone smoke against the running stack. From backend/:

    uv run python -m scripts.smoke

Needs `docker compose up -d --build` first. Makes real Claude calls: about $0.003 for m2-m6,
and up to $0.02 more for m7 (Sonnet reviews the draft).
Exit code 1 if any check failed. `python -m scripts.smoke m4` runs only milestones matching "m4".
"""

import sys
from collections.abc import Callable

from scripts.smoke import m2_tickets, m3_team, m4_triage, m5_assignment, m6_dashboards, m7_split
from scripts.smoke.common import reset_signup_limits

SUITES: dict[str, Callable[[], bool]] = {
    "m2": m2_tickets.main,
    "m3": m3_team.main,
    "m4": m4_triage.main,
    "m5": m5_assignment.main,
    "m6": m6_dashboards.main,
    "m7": m7_split.main,
}


def run(selected: list[str]) -> bool:
    results: dict[str, bool] = {}
    for name, suite in SUITES.items():
        if selected and not any(s in name for s in selected):
            continue
        reset_signup_limits()  # each suite signs up several people
        print(f"=== {name}")
        results[name] = suite()
    print("  ".join(f"{name}: {'ok' if ok else 'FAILED'}" for name, ok in results.items()))
    return all(results.values())


if __name__ == "__main__":
    raise SystemExit(0 if run(sys.argv[1:]) else 1)
