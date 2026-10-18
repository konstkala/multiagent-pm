"""Milestone 2: the ticket workflow, sub-tasks, links, comments and attachments."""

import hashlib

from scripts.smoke.common import (
    Json,
    account,
    check,
    email,
    page_ok,
    summary,
    workspace_with_project,
)


def main() -> bool:
    mgr = account(email("mgr-m2"), "Mia Manager")
    emp = account(email("emp-m2"), "Eli Employee")
    emp_id = emp.get("/auth/me").json()["id"]
    _, project = workspace_with_project(mgr, "Smoke M2", "SM")
    pid = project["id"]
    added = mgr.post(f"/projects/{pid}/members", json={"email": email("emp-m2")})
    check("manager adds an employee", added.status_code == 201)

    t: Json = mgr.post(
        f"/projects/{pid}/tickets",
        json={
            "title": "Login returns 500",
            "category": "bug",
            "priority": "high",
            "story_points": 5,
            "due_date": "2026-11-30",
            "labels": ["auth"],
            "assignee_id": emp_id,
        },
    ).json()
    url = f"/tickets/{t['id']}"
    check("create a ticket with all fields", t.get("number") == 1 and t.get("story_points") == 5)
    denied = emp.post(f"/projects/{pid}/tickets", json={"title": "x"})
    check("employee can't create tickets", denied.status_code == 403)
    moved = emp.patch(url, json={"status": "in_progress"})
    check("employee moves own ticket to in progress", moved.status_code == 200)
    review = emp.patch(url, json={"status": "in_review"})
    check("employee moves own ticket to review", review.status_code == 200)
    check("employee can't mark done", emp.patch(url, json={"status": "done"}).status_code == 403)
    check("manager marks done", mgr.patch(url, json={"status": "done"}).status_code == 200)

    parent: Json = mgr.post(
        f"/projects/{pid}/tickets", json={"title": "Checkout redesign", "assignee_id": emp_id}
    ).json()
    sub: Json = mgr.post(
        f"/projects/{pid}/tickets", json={"title": "Payment form", "parent_id": parent["id"]}
    ).json()
    subs = mgr.get(f"/projects/{pid}/tickets", params={"parent_id": parent["id"]}).json()["items"]
    check("sub-task listed under its parent", [s["id"] for s in subs] == [sub["id"]])
    link = mgr.post(f"/tickets/{sub['id']}/links", json={"target_id": t["id"], "type": "blocks"})
    incoming = mgr.get(f"{url}/links").json()
    check(
        "link shows on both tickets",
        link.status_code == 201 and incoming[0]["direction"] == "incoming",
    )
    comment = emp.post(f"/tickets/{parent['id']}/comments", json={"body": "Starting today"})
    check("employee comments", comment.status_code == 201)
    copy: Json = mgr.post(f"{url}/copy").json()
    check("manager copies a ticket", copy.get("title") == "Copy of Login returns 500")
    returned: Json = emp.post(
        f"/tickets/{parent['id']}/return", json={"reason": "Blocked by the payment provider"}
    ).json()
    check("employee returns a ticket", returned.get("assignee_id") is None)
    filtered = mgr.get(
        f"/projects/{pid}/tickets", params={"status": ["done"], "label": "auth"}
    ).json()["items"]
    check("filters through the proxy", [x["id"] for x in filtered] == [t["id"]])

    # A file just under the 10 MB limit, through the Next.js proxy into object storage and back.
    big = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * (int(9.5 * 2**20) // 256)
    up = emp.post(f"{url}/attachments", files={"file": ("proof.png", big, "image/png")})
    check("9.5 MB upload through the proxy", up.status_code == 201)
    down = emp.get(f"/attachments/{up.json()['id']}/download")
    same = hashlib.sha256(down.content).digest() == hashlib.sha256(big).digest()
    check("download is byte-identical (sha256)", same)
    check("download is sandboxed", down.headers.get("content-security-policy") == "sandbox")
    too_big = emp.post(
        f"{url}/attachments", files={"file": ("big.png", big + b"\x00" * 2**20, "image/png")}
    )
    check("10.5 MB refused", too_big.status_code == 413)
    html = emp.post(f"{url}/attachments", files={"file": ("x.html", b"<script>", "text/html")})
    check("HTML refused", html.status_code == 422)

    for path in (f"/projects/{pid}", f"/projects/{pid}/board", f"/projects/{pid}{url}"):
        check(f"page {path.replace(pid, '{p}').replace(t['id'], '{t}')}", page_ok(mgr, path))
    return summary("M2 tickets")


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
