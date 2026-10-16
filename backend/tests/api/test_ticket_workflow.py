from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import Login

pytestmark = pytest.mark.db


async def create(client: AsyncClient, project_id: str, **fields: Any) -> dict[str, Any]:
    response = await client.post(
        f"/projects/{project_id}/tickets", json={"title": "Fix the login", **fields}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def user_id(client: AsyncClient) -> str:
    return (await client.get("/auth/me")).json()["id"]


async def assigned_ticket(manager: AsyncClient, employee: AsyncClient, project_id: str) -> str:
    ticket = await create(manager, project_id, assignee_id=await user_id(employee))
    return ticket["id"]


# --- who may do what -------------------------------------------------------------------------


async def test_employees_read_but_cannot_create_tickets(
    manager: AsyncClient, employee: AsyncClient, project_id: str
) -> None:
    ticket = await create(manager, project_id)

    created = await employee.post(f"/projects/{project_id}/tickets", json={"title": "Mine"})
    read = await employee.get(f"/tickets/{ticket['id']}")

    assert created.status_code == 403
    assert read.status_code == 200


async def test_assignee_moves_own_ticket_through_the_working_statuses(
    manager: AsyncClient, employee: AsyncClient, project_id: str
) -> None:
    ticket_id = await assigned_ticket(manager, employee, project_id)

    for status in ("in_progress", "in_review", "in_progress", "in_review"):
        response = await employee.patch(f"/tickets/{ticket_id}", json={"status": status})
        assert response.status_code == 200, status


async def test_only_managers_close_or_reopen(
    manager: AsyncClient, employee: AsyncClient, project_id: str
) -> None:
    ticket_id = await assigned_ticket(manager, employee, project_id)
    url = f"/tickets/{ticket_id}"

    employee_done = await employee.patch(url, json={"status": "done"})
    employee_cancel = await employee.patch(url, json={"status": "cancelled"})
    manager_done = await manager.patch(url, json={"status": "done"})
    employee_reopen = await employee.patch(url, json={"status": "in_progress"})

    assert employee_done.status_code == employee_cancel.status_code == 403
    assert manager_done.status_code == 200
    assert employee_reopen.status_code == 403


async def test_employees_cannot_move_others_tickets_or_edit_fields(
    manager: AsyncClient, employee: AsyncClient, project_id: str
) -> None:
    unassigned = await create(manager, project_id)
    mine = await assigned_ticket(manager, employee, project_id)

    move_other = await employee.patch(
        f"/tickets/{unassigned['id']}", json={"status": "in_progress"}
    )
    edit_mine = await employee.patch(f"/tickets/{mine}", json={"priority": "urgent"})

    assert move_other.status_code == edit_mine.status_code == 403


async def test_assignee_must_be_a_project_member(
    manager: AsyncClient, project_id: str, login: Login
) -> None:
    outsider = await login("outsider")

    response = await manager.post(
        f"/projects/{project_id}/tickets",
        json={"title": "x", "assignee_id": await user_id(outsider)},
    )

    assert response.status_code == 422


async def test_return_to_manager_unassigns_resets_and_records_the_reason(
    manager: AsyncClient, employee: AsyncClient, project_id: str
) -> None:
    ticket_id = await assigned_ticket(manager, employee, project_id)
    await employee.patch(f"/tickets/{ticket_id}", json={"status": "in_progress"})

    response = await employee.post(
        f"/tickets/{ticket_id}/return", json={"reason": "Needs the API spec first"}
    )
    comments = (await manager.get(f"/tickets/{ticket_id}/comments")).json()

    returned = response.json()
    assert response.status_code == 200
    assert (returned["assignee_id"], returned["status"]) == (None, "todo")
    assert comments[-1]["body"] == "Returned to manager: Needs the API spec first"
    assert comments[-1]["author_name"] == "Emp"


async def test_only_the_assignee_can_return_a_ticket(
    manager: AsyncClient, employee: AsyncClient, project_id: str
) -> None:
    ticket = await create(manager, project_id)

    response = await employee.post(f"/tickets/{ticket['id']}/return", json={"reason": "Not mine"})

    assert response.status_code == 403


async def test_copy_keeps_content_and_sizing_but_not_work_state(
    manager: AsyncClient, employee: AsyncClient, project_id: str
) -> None:
    source = await create(
        manager,
        project_id,
        description="Steps",
        category="bug",
        labels=["auth"],
        story_points=3,
        assignee_id=await user_id(employee),
    )
    await manager.patch(f"/tickets/{source['id']}", json={"status": "in_progress"})

    copy = (await manager.post(f"/tickets/{source['id']}/copy")).json()
    employee_copy = await employee.post(f"/tickets/{source['id']}/copy")

    assert copy["title"] == "Copy of Fix the login"
    assert copy["number"] == source["number"] + 1
    assert (copy["category"], copy["labels"], copy["story_points"]) == ("bug", ["auth"], 3)
    assert (copy["status"], copy["assignee_id"]) == ("todo", None)
    assert employee_copy.status_code == 403


# --- sub-tasks -------------------------------------------------------------------------------


async def test_sub_tasks_are_listed_under_their_parent(
    manager: AsyncClient, project_id: str
) -> None:
    parent = await create(manager, project_id, title="Epic-ish")
    child = await create(manager, project_id, title="Part 1", parent_id=parent["id"])
    await create(manager, project_id, title="Unrelated")

    page = (
        await manager.get(f"/projects/{project_id}/tickets", params={"parent_id": parent["id"]})
    ).json()

    assert [t["id"] for t in page["items"]] == [child["id"]]


async def test_sub_tasks_are_one_level_deep(manager: AsyncClient, project_id: str) -> None:
    parent = await create(manager, project_id)
    child = await create(manager, project_id, parent_id=parent["id"])
    other = await create(manager, project_id)

    grandchild = await manager.post(
        f"/projects/{project_id}/tickets", json={"title": "x", "parent_id": child["id"]}
    )
    parent_under_other = await manager.patch(
        f"/tickets/{parent['id']}", json={"parent_id": other["id"]}
    )

    assert grandchild.status_code == parent_under_other.status_code == 422


# --- links -----------------------------------------------------------------------------------


async def test_links_show_on_both_tickets(manager: AsyncClient, project_id: str) -> None:
    blocker = await create(manager, project_id, title="API")
    blocked = await create(manager, project_id, title="UI")

    added = await manager.post(
        f"/tickets/{blocker['id']}/links", json={"target_id": blocked["id"], "type": "blocks"}
    )
    on_blocker = (await manager.get(f"/tickets/{blocker['id']}/links")).json()
    on_blocked = (await manager.get(f"/tickets/{blocked['id']}/links")).json()

    assert added.status_code == 201
    assert [(link["direction"], link["ticket"]["title"]) for link in on_blocker] == [
        ("outgoing", "UI")
    ]
    assert [(link["direction"], link["ticket"]["title"]) for link in on_blocked] == [
        ("incoming", "API")
    ]


async def test_link_rules(manager: AsyncClient, employee: AsyncClient, project_id: str) -> None:
    a = await create(manager, project_id)
    b = await create(manager, project_id)
    url = f"/tickets/{a['id']}/links"
    body = {"target_id": b["id"], "type": "relates_to"}

    first = await manager.post(url, json=body)
    again = await manager.post(url, json=body)
    to_self = await manager.post(url, json={"target_id": a["id"], "type": "blocks"})
    by_employee = await employee.post(url, json={"target_id": b["id"], "type": "blocks"})
    removed = await manager.delete(f"/links/{first.json()['id']}")

    assert again.status_code == 409
    assert to_self.status_code == 422
    assert by_employee.status_code == 403
    assert removed.status_code == 204


# --- comments --------------------------------------------------------------------------------


async def test_comments_edit_and_delete_rules(
    manager: AsyncClient, employee: AsyncClient, project_id: str
) -> None:
    ticket = await create(manager, project_id)
    url = f"/tickets/{ticket['id']}/comments"
    mine = (await employee.post(url, json={"body": "On it"})).json()
    managers = (await manager.post(url, json={"body": "Thanks"})).json()

    edited = await employee.patch(f"/comments/{mine['id']}", json={"body": "On it, ETA Friday"})
    edit_others = await employee.patch(f"/comments/{managers['id']}", json={"body": "hacked"})
    delete_others = await employee.delete(f"/comments/{managers['id']}")
    manager_deletes = await manager.delete(f"/comments/{mine['id']}")

    assert edited.json()["body"] == "On it, ETA Friday"
    assert edited.json()["edited_at"] is not None
    assert edit_others.status_code == delete_others.status_code == 403
    assert manager_deletes.status_code == 204
    assert [c["body"] for c in (await manager.get(url)).json()] == ["Thanks"]


async def test_outsiders_cannot_see_comments(
    manager: AsyncClient, project_id: str, login: Login
) -> None:
    ticket = await create(manager, project_id)
    comment = (
        await manager.post(f"/tickets/{ticket['id']}/comments", json={"body": "secret"})
    ).json()
    outsider = await login("outsider")

    listed = await outsider.get(f"/tickets/{ticket['id']}/comments")
    edited = await outsider.patch(f"/comments/{comment['id']}", json={"body": "x"})

    assert listed.status_code == edited.status_code == 404


# --- filters ---------------------------------------------------------------------------------


async def test_list_filters(manager: AsyncClient, employee: AsyncClient, project_id: str) -> None:
    emp = await user_id(employee)
    login_bug = await create(
        manager, project_id, title="Login 500", category="bug", labels=["auth"], assignee_id=emp
    )
    await create(manager, project_id, title="Dark mode", category="implementation")
    await manager.patch(f"/tickets/{login_bug['id']}", json={"status": "in_progress"})
    url = f"/projects/{project_id}/tickets"

    async def titles(**params: Any) -> list[str]:
        return [t["title"] for t in (await manager.get(url, params=params)).json()["items"]]

    assert await titles(status=["in_progress", "in_review"]) == ["Login 500"]
    assert await titles(assignee_id=emp) == ["Login 500"]
    assert await titles(unassigned=True) == ["Dark mode"]
    assert await titles(category="implementation") == ["Dark mode"]
    assert await titles(label="AUTH") == ["Login 500"]
    assert await titles(q="dark") == ["Dark mode"]
    assert await titles(q=str(login_bug["number"])) == ["Login 500"]
    assert await titles(q="100%") == []  # wildcards are literal text
