"""Shared helpers: accounts through the real sign-up flow, Mailpit tokens, checks and polling.

Everything goes through the web app's /api proxy (localhost:3000), like a browser. Development
stack only: never point these at a real deployment (they reset sign-up rate limits).
"""

import re
import subprocess
import time
from typing import Any

import httpx

WEB = "http://localhost:3000"
API = f"{WEB}/api"
MAILPIT = "http://localhost:8025/api/v1"
HEADERS = {"x-requested-with": "fetch"}  # the API's CSRF guard
PASSWORD = "correct horse battery"
RUN = str(int(time.time()))  # unique emails per run

Json = dict[str, Any]
_results: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    _results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}")


def summary(title: str) -> bool:
    passed = sum(ok for _, ok in _results)
    print(f"\n{title}: {passed}/{len(_results)} passed\n")
    all_ok = passed == len(_results)
    _results.clear()
    return all_ok


def email(name: str) -> str:
    return f"{name}-{RUN}@example.com"


def latest_token(address: str, subject_part: str) -> str:
    """The token from the newest email to `address` whose subject contains `subject_part`."""
    for _ in range(30):
        found = httpx.get(f"{MAILPIT}/search", params={"query": f"to:{address}"}).json()
        for message in found["messages"]:
            if subject_part in message["Subject"]:
                text = httpx.get(f"{MAILPIT}/message/{message['ID']}").json()["Text"]
                match = re.search(r"token=([\w-]+)", text)
                if match:
                    return match.group(1)
        time.sleep(0.3)
    raise RuntimeError(f"no '{subject_part}' email for {address}")


def account(address: str, name: str) -> httpx.Client:
    """Signs up, confirms the email, signs in. Returns a client that sends the session cookie."""
    client = httpx.Client(base_url=API, headers=HEADERS, timeout=60)
    client.post(
        "/auth/sign-up", json={"email": address, "password": PASSWORD, "display_name": name}
    )
    token = latest_token(address, "Confirm")
    client.post("/auth/verify-email", json={"token": token}).raise_for_status()
    signed_in = client.post("/auth/sign-in", json={"email": address, "password": PASSWORD})
    signed_in.raise_for_status()
    # Python's cookie jar won't send Secure cookies to http://localhost (browsers do).
    match = re.search(r"pm_session=([^;]+)", signed_in.headers["set-cookie"])
    if match is None:
        raise RuntimeError("sign-in set no session cookie")
    client.headers["cookie"] = f"pm_session={match.group(1)}"
    return client


def invite(manager: httpx.Client, project_id: str, name: str, display_name: str) -> httpx.Client:
    """Invites `name` as an employee, then they sign up and accept, like a real newcomer."""
    address = email(name)
    manager.post(
        f"/projects/{project_id}/invitations", json={"email": address, "role": "employee"}
    ).raise_for_status()
    token = latest_token(address, "invited you")
    client = account(address, display_name)
    client.post("/invitations/accept", json={"token": token}).raise_for_status()
    return client


def workspace_with_project(manager: httpx.Client, name: str, key: str) -> tuple[Json, Json]:
    workspace: Json = manager.post("/workspaces", json={"name": name}).json()
    project: Json = manager.post(
        f"/workspaces/{workspace['id']}/projects", json={"key": key, "name": name}
    ).json()
    return workspace, project


def wait_until_not(client: httpx.Client, url: str, busy: str, timeout: float = 60) -> Json:
    """Polls like the UI does until the run's status is no longer `busy`."""
    started = time.time()
    while time.time() - started < timeout:
        run: Json | None = client.get(url).json()
        if run and run["status"] != busy:
            return run
        time.sleep(1)
    raise RuntimeError(f"{url} still {busy} after {timeout:.0f} s")


def page_ok(client: httpx.Client, path: str) -> bool:
    cookie = client.headers["cookie"]
    return httpx.get(f"{WEB}{path}", headers={"cookie": cookie}, timeout=60).status_code == 200


def reset_signup_limits() -> None:
    """Each run creates several accounts; the sign-up limit (10 per hour per IP) would stop the
    next one. Clears only those counters, only in the local development database."""
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "pm",
            "-d",
            "pm",
            "-qc",
            "DELETE FROM rate_limit_buckets WHERE key LIKE 'sign_up:ip:%'",
        ],
        check=True,
    )
