"""Milestone 6: history → project dashboard, agent metrics, my work and the calendar."""

import statistics
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


def main() -> bool:
    today = date.today()
    mgr = account(email("mgr-m6"), "Mia Manager")
    _, project = workspace_with_project(mgr, "Smoke M6", "M6")
    pid = project["id"]
    emp = invite(mgr, pid, "emp-m6", "Eli Employee")
    emp_id = emp.get("/auth/me").json()["id"]

    def create(**fields: object) -> str:
        created = mgr.post(f"/projects/{pid}/tickets", json=fields)
        created.raise_for_status()
        return created.json()["id"]

    soon = (today + timedelta(days=2)).isoformat()
    shipped = create(title="Rotate the TLS certificates", assignee_id=emp_id, story_points=3)
    emp.patch(f"/tickets/{shipped}", json={"status": "in_progress"}).raise_for_status()
    mgr.patch(f"/tickets/{shipped}", json={"status": "done"}).raise_for_status()
    mine_due = create(title="Patch the database server", assignee_id=emp_id, due_date=soon)
    other_due = create(title="Renew the domain name", due_date=soon)
    bug = create(
        title="Login page returns 500 after password reset", description="Since the deploy."
    )

    run = wait_until_not(mgr, f"/tickets/{bug}/triage", "queued")
    check("triage proposed on a new ticket", run["status"] == "proposed")
    proposal: Json = run["proposal"]
    edited = "low" if proposal["priority"] != "low" else "urgent"
    mgr.post(
        f"/triage-runs/{run['id']}/accept",
        json={"category": proposal["category"], "priority": edited},
    ).raise_for_status()
    suggested: Json = mgr.post(f"/tickets/{bug}/assignment-suggestions").json()
    wait_until_not(mgr, f"/tickets/{bug}/assignment-suggestions", "explaining")
    first = suggested["candidates"][0]["user_id"]
    mgr.patch(f"/tickets/{bug}", json={"assignee_id": first}).raise_for_status()

    board: Json = mgr.get(f"/projects/{pid}/dashboard").json()
    check("dashboard counts created and done", (board["created"], board["done"]) == (4, 1))
    check("cycle time from real events", board["cycle_time"]["tickets"] == 1)
    people = {r["display_name"] for r in board["workload"]}
    check("manager sees everyone's workload", people == {"Mia Manager", "Eli Employee"})
    own = emp.get(f"/projects/{pid}/dashboard").json()["workload"]
    check("employee sees only their own row", [r["display_name"] for r in own] == ["Eli Employee"])

    metrics: Json = mgr.get(f"/projects/{pid}/agent-metrics").json()
    fields = {f["field"]: f for f in metrics["triage"]["fields"]}
    check("metrics: the edited priority counts as edited", fields["priority"]["edited"] == 1)
    check("metrics: labels left out", fields["labels"]["left_out"] == 1)
    check("metrics: first suggestion picked = 100% hit", metrics["assignment"]["top1_rate"] == 1.0)
    denied = emp.get(f"/projects/{pid}/agent-metrics")
    check("employee can't see agent metrics (403)", denied.status_code == 403)

    my: Json = emp.get("/me/dashboard").json()
    check("my work: due soon and done", [t["id"] for t in my["due_soon"]] == [mine_due])
    window = {"start": today.isoformat(), "end": (today + timedelta(days=30)).isoformat()}
    everything = {t["id"] for t in emp.get("/calendar", params=window).json()}
    mine = [t["id"] for t in emp.get("/calendar", params=window | {"mine": True}).json()]
    check(
        "calendar: my projects' due tickets; 'mine' filters",
        everything == {mine_due, other_due} and mine == [mine_due],
    )
    for path in (f"/projects/{pid}/dashboard", "/me", "/calendar"):
        check(f"page {path.replace(pid, '{p}')} renders", page_ok(mgr, path))

    timings: list[float] = []
    for _ in range(20):
        t0 = time.perf_counter()
        mgr.get(f"/projects/{pid}/dashboard").raise_for_status()
        timings.append((time.perf_counter() - t0) * 1000)
    p95 = statistics.quantiles(timings, n=20)[-1]
    print(f"      dashboard p50 {statistics.median(timings):.0f} ms, p95 {p95:.0f} ms")
    check("dashboard p95 within 300 ms", p95 <= 300)
    return summary("M6 dashboards")


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
