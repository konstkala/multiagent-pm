"""Demo data for the local stack, so every screen has something to show.

    docker compose up -d --wait
    cd backend && uv run python -m scripts.seed_demo

Creates (or reuses) a manager, three teammates with profiles, a project and a dozen tickets
with some history. Sign in at http://localhost:3000 as demo-manager@example.com with the
password printed at the end. Development stack only. New tickets are triaged by the real agent
(about $0.0001 each).
"""

import re
import time
from datetime import date, timedelta

import httpx

from scripts.smoke.common import (
    API,
    HEADERS,
    PASSWORD,
    Json,
    account,
    latest_token,
    reset_signup_limits,
)

MANAGER = ("demo-manager@example.com", "Mia Manager")
TEAM = [
    (
        "demo-ana@example.com",
        "Ana Costa",
        "Payments engineer",
        "Checkout, refunds and coupons; owns the payment service.",
        {"payments": 5, "Python": 4},
    ),
    (
        "demo-ben@example.com",
        "Ben Okafor",
        "Frontend developer",
        "React and TypeScript interfaces, accessibility, design systems.",
        {"React": 5, "TypeScript": 4},
    ),
    (
        "demo-cara@example.com",
        "Cara Lindqvist",
        "Backend developer",
        "APIs, databases and background jobs.",
        {"Python": 5, "PostgreSQL": 4, "payments": 3},
    ),
]
# title, description, labels, points, due in days, assignee index (None = nobody), final status
type Row = tuple[str, str, list[str], int | None, int | None, int | None, str]
TICKETS: list[Row] = [
    (
        "Checkout fails with 500 when a discount code is applied",
        "Customers can't pay since the deploy.",
        ["payments"],
        3,
        1,
        0,
        "in_progress",
    ),
    (
        "Refund emails are sent twice",
        "Support reports duplicate refund confirmations.",
        ["payments", "email"],
        2,
        4,
        0,
        "todo",
    ),
    ("Coupon codes ignore the expiry date", "", ["payments"], 3, -2, 0, "in_review"),
    (
        "Board columns jump while dragging on Safari",
        "Reproduced on iOS 18.",
        ["frontend"],
        5,
        6,
        1,
        "in_progress",
    ),
    (
        "Add keyboard shortcuts to the ticket list",
        "J/K to move, Enter to open.",
        ["frontend", "a11y"],
        5,
        14,
        1,
        "todo",
    ),
    ("Dark mode: charts lose contrast", "", ["frontend"], 2, -1, 1, "done"),
    (
        "Slow query on the tickets search",
        "p95 is 900 ms with 50k tickets.",
        ["database", "performance"],
        8,
        9,
        2,
        "in_progress",
    ),
    ("Retry failed webhook deliveries with backoff", "", ["backend"], 5, 12, 2, "todo"),
    (
        "Migrate attachments to object storage",
        "Done for new files, old ones remain.",
        ["backend", "storage"],
        8,
        -6,
        2,
        "done",
    ),
    ("Make it faster", "", [], None, None, None, "todo"),
    (
        "Write the on-call runbook",
        "How to read the logs and roll back.",
        ["docs"],
        3,
        20,
        None,
        "todo",
    ),
    ("Upgrade Postgres to 17", "", ["database"], 5, 30, None, "todo"),
]


def sign_in_or_up(email: str, name: str) -> httpx.Client:
    client = httpx.Client(base_url=API, headers=HEADERS, timeout=60)
    signed_in = client.post("/auth/sign-in", json={"email": email, "password": PASSWORD})
    if signed_in.status_code != 200:
        return account(email, name)
    match = re.search(r"pm_session=([^;]+)", signed_in.headers["set-cookie"])
    assert match is not None
    client.headers["cookie"] = f"pm_session={match.group(1)}"
    return client


def main() -> None:
    reset_signup_limits()
    mgr = sign_in_or_up(*MANAGER)
    workspaces: list[Json] = mgr.get("/workspaces").json()
    if not any(w["name"] == "Acme" for w in workspaces):
        workspace: Json = mgr.post("/workspaces", json={"name": "Acme"}).json()
    else:
        workspace = next(w for w in workspaces if w["name"] == "Acme")
    projects: list[Json] = mgr.get(f"/workspaces/{workspace['id']}/projects").json()
    if projects:
        print("Demo project already exists: nothing more to create.")
        return print_login()
    project: Json = mgr.post(
        f"/workspaces/{workspace['id']}/projects", json={"key": "PLAT", "name": "Platform"}
    ).json()
    pid = project["id"]

    ids: list[str] = []
    for email, name, headline, about, skills in TEAM:
        mgr.post(
            f"/projects/{pid}/invitations", json={"email": email, "role": "employee"}
        ).raise_for_status()
        token = latest_token(email, "invited you")
        person = sign_in_or_up(email, name)
        person.post("/invitations/accept", json={"token": token}).raise_for_status()
        user_id = person.get("/auth/me").json()["id"]
        ids.append(user_id)
        mgr.put(
            f"/workspaces/{workspace['id']}/people/{user_id}/profile",
            json={
                "headline": headline,
                "summary": about,
                "skills": [{"name": k, "level": v} for k, v in skills.items()],
            },
        ).raise_for_status()

    today = date.today()
    for title, description, labels, points, due, who, status in TICKETS:
        body: Json = {"title": title, "description": description, "labels": labels}
        if points:
            body["story_points"] = points
        if due is not None:
            body["due_date"] = (today + timedelta(days=due)).isoformat()
        if who is not None:
            body["assignee_id"] = ids[who]
        created = mgr.post(f"/projects/{pid}/tickets", json=body)
        created.raise_for_status()
        if status != "todo":
            for step in {
                "in_review": ["in_progress", "in_review"],
                "done": ["in_progress", "done"],
            }.get(status, [status]):
                mgr.patch(
                    f"/tickets/{created.json()['id']}", json={"status": step}
                ).raise_for_status()
        time.sleep(0.3)  # triage jobs are picked up in order; don't flood the worker
    print_login()


def print_login() -> None:
    print("\nDemo ready: http://localhost:3000")
    print(f"  manager:  {MANAGER[0]}   password: {PASSWORD}")
    print(f"  employee: {TEAM[0][0]}   password: {PASSWORD}")
    print("Triage runs in the background: give it ~30 s, then open a ticket.")


if __name__ == "__main__":
    main()
