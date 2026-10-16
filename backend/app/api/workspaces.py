import uuid
from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ErrorResponse
from app.db.models import Project, ProjectRole, User, WorkspaceRole
from app.schemas.workspaces import (
    MemberAdd,
    MemberRead,
    ProjectCreate,
    ProjectRead,
    RoleUpdate,
    WorkspaceCreate,
    WorkspaceRead,
)
from app.services import access, workspaces

router = APIRouter(tags=["workspaces"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (403, 404, 409, 422)
}


def _project(project: Project, role: ProjectRole) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        workspace_id=project.workspace_id,
        key=project.key,
        name=project.name,
        description=project.description,
        role=role,
    )


def _member(user: User, role: ProjectRole) -> MemberRead:
    return MemberRead(user_id=user.id, display_name=user.display_name, email=user.email, role=role)


@router.post("/workspaces", status_code=status.HTTP_201_CREATED)
async def create_workspace(
    data: WorkspaceCreate, session: SessionDep, user: CurrentUser
) -> WorkspaceRead:
    workspace = await workspaces.create_workspace(session, data.name, user)
    return WorkspaceRead(id=workspace.id, name=workspace.name, role=WorkspaceRole.OWNER)


@router.get("/workspaces")
async def list_workspaces(session: SessionDep, user: CurrentUser) -> list[WorkspaceRead]:
    return [
        WorkspaceRead(id=w.id, name=w.name, role=role)
        for w, role in await workspaces.list_workspaces(session, user)
    ]


@router.post(
    "/workspaces/{workspace_id}/projects", status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
async def create_project(
    workspace_id: uuid.UUID, data: ProjectCreate, session: SessionDep, user: CurrentUser
) -> ProjectRead:
    project = await workspaces.create_project(
        session,
        workspace_id,
        key=data.key,
        name=data.name,
        description=data.description,
        user=user,
    )
    return _project(project, ProjectRole.MANAGER)


@router.get("/workspaces/{workspace_id}/projects", responses=_ERRORS)
async def list_projects(
    workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[ProjectRead]:
    return [
        _project(p, role) for p, role in await workspaces.list_projects(session, workspace_id, user)
    ]


@router.get("/projects/{project_id}", responses=_ERRORS)
async def get_project(project_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> ProjectRead:
    project = await access.get_project(session, project_id, user)
    return _project(project, await access.project_role(session, project_id, user))


@router.get("/projects/{project_id}/members", responses=_ERRORS)
async def list_members(
    project_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[MemberRead]:
    return [
        _member(u, role) for u, role in await workspaces.list_members(session, project_id, user)
    ]


@router.post(
    "/projects/{project_id}/members", status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
async def add_member(
    project_id: uuid.UUID, data: MemberAdd, session: SessionDep, user: CurrentUser
) -> MemberRead:
    member = await workspaces.add_member(
        session, project_id, email=data.email, role=data.role, actor=user
    )
    return _member(member, data.role)


@router.patch(
    "/projects/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
)
async def change_role(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    data: RoleUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    await workspaces.change_role(session, project_id, user_id, data.role, user)


@router.delete(
    "/projects/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
)
async def remove_member(
    project_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    await workspaces.remove_member(session, project_id, user_id, user)
