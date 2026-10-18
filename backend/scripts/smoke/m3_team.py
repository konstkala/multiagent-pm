"""Milestone 3: invitations, and a CV read by the worker and real Haiku, reviewed by a manager."""

import time

import httpx

from scripts.smoke.common import (
    API,
    HEADERS,
    WEB,
    Json,
    account,
    check,
    email,
    latest_token,
    page_ok,
    summary,
    workspace_with_project,
)
from tests.fakes import minimal_pdf


def main() -> bool:
    mgr = account(email("mgr-m3"), "Mia Manager")
    workspace, project = workspace_with_project(mgr, "Smoke M3", "M3")
    ws, pid = workspace["id"], project["id"]

    invited = mgr.post(
        f"/projects/{pid}/invitations", json={"email": email("new-m3"), "role": "employee"}
    )
    check("manager sends an invitation", invited.status_code == 201)
    token = latest_token(email("new-m3"), "invited you")
    preview: Json = httpx.post(
        f"{API}/invitations/preview", json={"token": token}, headers=HEADERS
    ).json()
    check("invite preview works before sign-in", preview.get("status") == "pending")
    newbie = account(email("new-m3"), "Nia Newcomer")
    intruder = account(email("intruder-m3"), "Ivan Intruder")
    stolen = intruder.post("/invitations/accept", json={"token": token})
    check("a forwarded link is refused for another account", stolen.status_code == 403)
    accepted = newbie.post("/invitations/accept", json={"token": token})
    check("the invited person accepts", accepted.status_code == 200)
    newbie_id = newbie.get("/auth/me").json()["id"]

    cv = minimal_pdf(
        "Nia Newcomer - nia@example.com",
        "Frontend engineer, 2019-2025 at Webco",
        "Built React and TypeScript apps; design systems with Tailwind CSS",
        "Wrote end-to-end tests with Playwright; some Node.js APIs",
    )
    started = mgr.post(
        f"/workspaces/{ws}/people/{newbie_id}/cv", files={"file": ("cv.pdf", cv, "application/pdf")}
    )
    check("CV accepted for processing (202)", started.status_code == 202)
    import_id = started.json()["id"]
    t0 = time.time()
    current: Json = started.json()
    while current["status"] == "queued" and time.time() - t0 < 60:
        time.sleep(1)
        current = mgr.get(f"/cv-imports/{import_id}").json()
    check(
        f"worker + Haiku drafted a profile ({time.time() - t0:.1f} s)",
        current["status"] == "needs_review",
    )
    draft: Json = current["draft"]
    skills = {s["name"].lower() for s in draft["skills"]}
    print(f"      cost ${current['cost_usd']:.5f}, {current['latency_ms'] / 1000:.1f} s")
    check("the draft found React and TypeScript", {"react", "typescript"} <= skills)
    check(
        "no name or email in the draft", "nia" not in (draft["headline"] + draft["summary"]).lower()
    )
    check(
        "the employee can't see the import",
        newbie.get(f"/cv-imports/{import_id}").status_code == 403,
    )
    approved: Json = mgr.post(
        f"/cv-imports/{import_id}/approve",
        json={
            "headline": draft["headline"],
            "summary": draft["summary"],
            "years_experience": draft["years_experience"],
            "skills": [{"name": s["name"], "level": s["level"]} for s in draft["skills"]],
        },
    ).json()
    check("manager approves; the draft is deleted", approved.get("draft") is None)
    own = newbie.get(f"/workspaces/{ws}/people/{newbie_id}/profile").json()
    check("the employee sees their saved profile", len(own["skills"]) == len(draft["skills"]))

    for path in (f"/people/{ws}", f"/people/{ws}/{newbie_id}", f"/projects/{pid}/team"):
        check("page renders", page_ok(mgr, path))
    check("invite page loads", httpx.get(f"{WEB}/invite?token={token}").status_code == 200)
    return summary("M3 team")


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
