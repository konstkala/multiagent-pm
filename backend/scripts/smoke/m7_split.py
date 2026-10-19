"""Milestone 7: the splitter graph. Haiku drafts → Sonnet critiques → pause → manager keeps some."""

import time

import httpx

from scripts.smoke.common import (
    Json,
    account,
    check,
    email,
    invite,
    page_ok,
    summary,
    workspace_with_project,
)

SONNET = "claude-sonnet-5-5"


def wait_for(client: httpx.Client, url: str, wanted: set[str], timeout: float = 120) -> Json:
    """Polls like the UI does, printing each graph step as it appears."""
    started, seen = time.time(), None
    while time.time() - started < timeout:
        run: Json | None = client.get(url).json()
        if run and (run["status"], run["step"]) != seen:
            seen = (run["status"], run["step"])
            print(f"      {time.time() - started:5.1f} s  {run['status']} / {run['step']}")
        if run and run["status"] in wanted:
            return run
        time.sleep(1)
    raise RuntimeError(f"{url} not in {wanted} after {timeout:.0f} s")


def main() -> bool:
    mgr = account(email("mgr-m7"), "Mia Manager")
    _, project = workspace_with_project(mgr, "Smoke M7", "M7")
    pid = project["id"]
    emp = invite(mgr, pid, "emp-m7", "Eli Employee")

    def create(**fields: object) -> Json:
        created = mgr.post(f"/projects/{pid}/tickets", json=fields)
        created.raise_for_status()
        return created.json()

    big = create(
        title="Build the billing module",
        description=(
            "Customers need invoices (PDF, numbered, per month), card payments with refunds, "
            "and a portal page where they download past invoices and update their card."
        ),
        story_points=13,
        category="implementation",
        priority="high",
        labels=["billing"],
    )
    small = create(title="Fix a typo in the footer", story_points=1)
    url = f"/tickets/{big['id']}/split"

    check("employee can't ask for a split (403)", emp.post(url).status_code == 403)
    check(
        "a 1-point ticket can't be split (409)",
        mgr.post(f"/tickets/{small['id']}/split").status_code == 409,
    )
    started = mgr.post(url)
    check("asking returns at once (202, queued)", started.status_code == 202)
    check("asking twice is refused (409)", mgr.post(url).status_code == 409)

    run = wait_for(mgr, url, {"proposed", "failed"})
    check("the graph pauses for the manager", run["status"] == "proposed")
    proposal: Json = run["proposal"]
    subs: list[Json] = proposal["sub_tickets"]
    for index, sub in enumerate(subs):
        print(f"      {index}. {sub['title']} ({sub['story_points']} pts)")
    if proposal["issues"]:
        print(f"      reviewer still worried: {proposal['issues']}")
    nodes = [c["node"] for c in run["calls"]]
    check(
        "2 to 5 sub-tickets, each smaller than the ticket",
        2 <= len(subs) <= 5 and all(s["story_points"] < 13 for s in subs),
    )
    check("draft then critique ran", nodes[:2] == ["draft", "critique"])
    check(
        "the critic is Sonnet, the writer is not",
        {c["node"]: c["model"] for c in run["calls"]}["critique"] == SONNET,
    )
    check(
        "nothing is created before the decision",
        mgr.get(f"/projects/{pid}/tickets", params={"parent_id": big["id"]}).json()["total"] == 0,
    )
    check("cost recorded and under the $0.05 budget", 0 < run["cost_usd"] < 0.05)

    keep = list(range(min(2, len(subs))))
    decided = mgr.post(f"/split-runs/{run['id']}/decide", json={"keep": keep})
    check("deciding returns at once (202)", decided.status_code == 202)
    check(
        "deciding twice is refused (409)",
        mgr.post(f"/split-runs/{run['id']}/decide", json={"keep": keep}).status_code == 409,
    )
    done = wait_for(mgr, url, {"applied", "failed"}, timeout=60)
    kids = mgr.get(f"/projects/{pid}/tickets", params={"parent_id": big["id"]}).json()["items"]
    check(
        "only the kept sub-tickets were created",
        done["status"] == "applied" and len(kids) == len(keep),
    )
    check(
        "they are sub-tasks that inherit category and labels",
        all(
            k["parent_id"] == big["id"]
            and k["category"] == "implementation"
            and k["labels"] == ["billing"]
            for k in kids
        ),
    )
    check(
        "each new sub-ticket is queued for triage",
        all(mgr.get(f"/tickets/{k['id']}/triage").json() is not None for k in kids),
    )
    check("ticket page renders", page_ok(mgr, f"/projects/{pid}/tickets/{big['id']}"))
    print(
        f"      {done['llm_calls']} calls, ${done['cost_usd']:.5f}, "
        f"{done['latency_ms'] / 1000:.1f} s of model time"
    )
    return summary("M7 split")


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
