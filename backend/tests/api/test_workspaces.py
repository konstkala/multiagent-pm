import logging

import pytest
from httpx import AsyncClient

from tests.conftest import Login

pytestmark = pytest.mark.db


async def workspace_id(client: AsyncClient) -> str:
    return (await client.get("/workspaces")).json()[0]["id"]


async def add(manager: AsyncClient, project_id: str, name: str, role: str = "employee") -> str:
    response = await manager.post(
        f"/projects/{project_id}/members", json={"email": f"{name}@example.com", "role": role}
    )
    assert response.status_code == 201
    return response.json()["user_id"]


async def test_creator_owns_workspace_and_manages_project(
    manager: AsyncClient, project_id: str
) -> None:
    workspaces = (await manager.get("/workspaces")).json()
    project = (await manager.get(f"/projects/{project_id}")).json()

    assert [(w["name"], w["role"]) for w in workspaces] == [("Acme", "owner")]
    assert (project["key"], project["role"]) == ("PM", "manager")


async def test_project_key_is_validated_and_unique_per_workspace(
    manager: AsyncClient, project_id: str
) -> None:
    url = f"/workspaces/{await workspace_id(manager)}/projects"

    lowercase = await manager.post(url, json={"key": "pm", "name": "x"})
    taken = await manager.post(url, json={"key": "PM", "name": "Again"})

    assert lowercase.status_code == 422
    assert taken.status_code == 409


async def test_added_employee_sees_project_and_its_tickets(
    manager: AsyncClient, project_id: str, login: Login
) -> None:
    employee = await login("emp")
    await add(manager, project_id, "emp")

    projects = (await employee.get(f"/workspaces/{await workspace_id(employee)}/projects")).json()
    tickets = await employee.get(f"/projects/{project_id}/tickets")

    assert [(p["key"], p["role"]) for p in projects] == [("PM", "employee")]
    assert tickets.status_code == 200


async def test_employees_cannot_manage_members_or_create_projects(
    manager: AsyncClient, project_id: str, login: Login
) -> None:
    employee = await login("emp")
    await login("other")
    await add(manager, project_id, "emp")

    add_member = await employee.post(
        f"/projects/{project_id}/members", json={"email": "other@example.com"}
    )
    new_project = await employee.post(
        f"/workspaces/{await workspace_id(employee)}/projects", json={"key": "X1", "name": "X"}
    )

    assert add_member.status_code == 403
    assert new_project.status_code == 403


async def test_outsiders_see_nothing(manager: AsyncClient, project_id: str, login: Login) -> None:
    outsider = await login("outsider")
    ws = await workspace_id(manager)

    assert (await outsider.get("/workspaces")).json() == []
    assert (await outsider.get(f"/projects/{project_id}")).status_code == 404
    assert (await outsider.get(f"/projects/{project_id}/members")).status_code == 404
    assert (await outsider.get(f"/workspaces/{ws}/projects")).status_code == 404


async def test_adding_unknown_or_existing_member_fails_clearly(
    manager: AsyncClient, project_id: str, login: Login
) -> None:
    await login("emp")
    await add(manager, project_id, "emp")
    url = f"/projects/{project_id}/members"

    unknown = await manager.post(url, json={"email": "nobody@example.com"})
    again = await manager.post(url, json={"email": "emp@example.com"})

    assert unknown.status_code == 404
    assert again.status_code == 409


async def test_project_always_keeps_one_manager(manager: AsyncClient, project_id: str) -> None:
    me = (await manager.get("/auth/me")).json()["id"]
    url = f"/projects/{project_id}/members/{me}"

    demote = await manager.patch(url, json={"role": "employee"})
    remove = await manager.delete(url)

    assert demote.status_code == remove.status_code == 422


async def test_promote_then_remove_member(
    manager: AsyncClient, project_id: str, login: Login
) -> None:
    employee = await login("emp")
    emp_id = await add(manager, project_id, "emp")

    promoted = await manager.patch(
        f"/projects/{project_id}/members/{emp_id}", json={"role": "manager"}
    )
    members = (await manager.get(f"/projects/{project_id}/members")).json()
    removed = await manager.delete(f"/projects/{project_id}/members/{emp_id}")

    assert promoted.status_code == 204
    assert {m["display_name"]: m["role"] for m in members} == {
        "Emp": "manager",
        "Manager": "manager",
    }
    assert removed.status_code == 204
    assert (await employee.get(f"/projects/{project_id}")).status_code == 404


async def test_membership_changes_are_audited(
    manager: AsyncClient, project_id: str, login: Login, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.services.workspaces")
    await login("emp")

    emp_id = await add(manager, project_id, "emp")
    await manager.patch(f"/projects/{project_id}/members/{emp_id}", json={"role": "manager"})
    await manager.delete(f"/projects/{project_id}/members/{emp_id}")

    events = [r.getMessage() for r in caplog.records]
    assert events == [
        "audit.project.member_added",
        "audit.project.role_changed",
        "audit.project.member_removed",
    ]
