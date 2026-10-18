"""Milestone 4: ticket → queue → worker → real Haiku triage → the manager decides."""

import httpx

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
    mgr = account(email("mgr-m4"), "Mia Manager")
    _, project = workspace_with_project(mgr, "Smoke M4", "M4")
    pid = project["id"]
    emp = invite(mgr, pid, "emp-m4", "Eli Employee")

    def create(**fields: object) -> Json:
        return mgr.post(f"/projects/{pid}/tickets", json=fields).json()

    def settled(client: httpx.Client, ticket_id: str) -> Json:
        return wait_until_not(client, f"/tickets/{ticket_id}/triage", "queued")

    first = create(
        title="Payment service returns 500 for discounted carts",
        description="Stack trace in payment-service when a coupon is applied.",
        labels=["payments", "backend"],
    )
    queued = mgr.get(f"/tickets/{first['id']}/triage").json()["status"] == "queued"
    check("creating a ticket queues triage", queued)
    settled(mgr, first["id"])

    second = create(
        title="Checkout fails with 500 when the cart has a discount code",
        description="Customers can't pay since this morning's deploy. Error in the payment logs.",
    )
    run = settled(mgr, second["id"])
    ticket: Json = mgr.get(f"/tickets/{second['id']}").json()
    proposal: Json = run["proposal"] or {}
    check("worker + Haiku produce a proposal", run["status"] == "proposed")
    check("confident category auto-applied to an empty field", "category" in run["auto_applied"])
    check("priority and points wait for a manager", ticket["priority"] is None)
    check("the agent reuses the project's labels", "payments" in proposal.get("labels", []))
    check("the agent links the likely duplicate", proposal.get("duplicate_of_id") == first["id"])
    check("run cost recorded and under budget", 0 < run["cost_usd"] < 0.05)

    denied = emp.post(f"/triage-runs/{run['id']}/accept", json={})
    check("employee can't accept (403)", denied.status_code == 403)
    body = {"priority": "urgent", "story_points": proposal["story_points"]}
    accepted = mgr.post(f"/triage-runs/{run['id']}/accept", json=body)
    after: Json = mgr.get(f"/tickets/{second['id']}").json()
    check("manager accepts with an edit", accepted.json()["status"] == "applied")
    check("accepted fields land on the ticket", after["priority"] == "urgent")
    again = mgr.post(f"/triage-runs/{run['id']}/accept", json={})
    check("accepting twice is refused (409)", again.status_code == 409)

    rerun = mgr.post(f"/tickets/{second['id']}/triage")
    check("manager re-runs (202)", rerun.status_code == 202)
    busy = mgr.post(f"/tickets/{second['id']}/triage")
    check("a second re-run while queued is refused (409)", busy.status_code == 409)
    repeat = settled(mgr, second["id"])
    check("a re-run doesn't touch fields a person set", repeat["auto_applied"] == [])
    dismissed = mgr.post(f"/triage-runs/{repeat['id']}/dismiss").json()
    check("manager dismisses", dismissed["status"] == "dismissed")

    vague = create(title="Make it faster", description="")
    asked = settled(mgr, vague["id"])
    if asked["status"] == "needs_answer":
        print(f"      the agent asked: {asked['question']}")
        no = emp.post(f"/triage-runs/{asked['id']}/answer", json={"answer": "x"})
        check("employee can't answer (403)", no.status_code == 403)
        mgr.post(
            f"/triage-runs/{asked['id']}/answer",
            json={"answer": "The board page with 300 tickets takes 6 s to load."},
        ).raise_for_status()
        final = settled(mgr, vague["id"])
        check("after the answer: a proposal, no second question", final["llm_calls"] == 2)
    else:
        print(f"      the agent didn't ask on the vague ticket ({asked['status']})")

    check("ticket page renders", page_ok(mgr, f"/projects/{pid}/tickets/{second['id']}"))
    return summary("M4 triage")


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
