"""Milestone 5: profiles + history + workload → ranking → Haiku reasons → the manager's pick."""

import time
from datetime import date, timedelta

from scripts.smoke.common import (
    Json,
    account,
    check,
    email,
    invite,
    page_ok,
    summary,
    wait_until_not,
    workspace_with_project,
)

PROFILES = {
    "Ana": (
        "Payments engineer",
        "Checkout and payment integrations, refunds, coupons.",
        {"payments": 5, "Python": 4},
    ),
    "Ben": (
        "Frontend developer",
        "React and TypeScript interfaces, design systems.",
        {"React": 4, "TypeScript": 4},
    ),
    "Cara": (
        "Backend developer",
        "Payment service and billing APIs.",
        {"payments": 4, "Python": 3},
    ),
}


def main() -> bool:
    mgr = account(email("mgr-m5"), "Mia Manager")
    workspace, project = workspace_with_project(mgr, "Smoke M5", "M5")
    ws, pid = workspace["id"], project["id"]
    team = {
        name: invite(mgr, pid, f"{name.lower()}-m5", f"{name} Teammate")
        .get("/auth/me")
        .json()["id"]
        for name in PROFILES
    }
    ana = invite(mgr, pid, "ana2-m5", "Ana Observer")  # an employee, for the permission check
    for name, (headline, about, skills) in PROFILES.items():
        mgr.put(
            f"/workspaces/{ws}/people/{team[name]}/profile",
            json={
                "headline": headline,
                "summary": about,
                "skills": [{"name": k, "level": v} for k, v in skills.items()],
            },
        ).raise_for_status()

    def create(**fields: object) -> Json:
        created = mgr.post(f"/projects/{pid}/tickets", json=fields)
        created.raise_for_status()
        return created.json()

    done = create(title="Coupon code makes the payment service return 500", assignee_id=team["Ana"])
    mgr.patch(f"/tickets/{done['id']}", json={"status": "done"}).raise_for_status()
    overdue = (date.today() - timedelta(days=4)).isoformat()
    for n in range(3):
        create(
            title=f"Billing export part {n}",
            assignee_id=team["Cara"],
            story_points=8,
            due_date=overdue,
        )
    bug = create(
        title="Checkout fails with 500 when a discount code is applied",
        description="Customers can't pay since this morning's deploy.",
        labels=["payments"],
    )
    url = f"/tickets/{bug['id']}/assignment-suggestions"

    check("employee can't ask for suggestions (403)", ana.post(url).status_code == 403)
    t0 = time.time()
    started = mgr.post(url)
    run: Json = started.json()
    names = [c["display_name"] for c in run["candidates"]]
    check("ranking comes back at once (202, reasons pending)", started.status_code == 202)
    check("the payments expert with past work ranks first", names[0] == "Ana Teammate")
    check("the swamped, late teammate isn't first", names[0] != "Cara Teammate")
    facts: Json = run["candidates"][0]["facts"]
    check("facts explain the score", facts["similar_done"] == 1)
    check("asking twice while writing is refused (409)", mgr.post(url).status_code == 409)

    run = wait_until_not(mgr, url, "explaining")
    reasons_s = time.time() - t0
    for c in run["candidates"]:
        print(f"      {c['rank']}. {c['display_name']}: {c['reason']}")
    check("worker + Haiku write a reason for each", all(c["reason"] for c in run["candidates"]))
    check("reasons within the 10 s interactive target", reasons_s <= 10)
    check("cost recorded and under budget", 0 < run["cost_usd"] < 0.05)

    pick = run["candidates"][0]["user_id"]
    mgr.patch(f"/tickets/{bug['id']}", json={"assignee_id": pick}).raise_for_status()
    check("assigning records the pick as rank 1", mgr.get(url).json()["chosen_rank"] == 1)
    check("ticket page renders", page_ok(mgr, f"/projects/{pid}/tickets/{bug['id']}"))
    print(f"      reasons after {reasons_s:.1f} s, ${run['cost_usd']:.5f}")
    return summary("M5 assignment")


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
