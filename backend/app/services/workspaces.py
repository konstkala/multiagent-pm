import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, InvalidRequestError, NotFoundError
from app.core.logging import log_fields
from app.db.models import (
    Project,
    ProjectMember,
    ProjectRole,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)
from app.services import access
from app.services.auth import normalize_email

logger = logging.getLogger(__name__)


async def create_workspace(session: AsyncSession, name: str, user: User) -> Workspace:
    workspace = Workspace(name=name, created_by=user.id)
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.OWNER)
    )
    await session.commit()
    logger.info(
        "audit.workspace.created", extra=log_fields(actor=user.id, workspace_id=workspace.id)
    )
    return workspace


async def list_workspaces(
    session: AsyncSession, user: User
) -> list[tuple[Workspace, WorkspaceRole]]:
    rows = await session.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.name)
    )
    return [(w, role) for w, role in rows]


async def create_project(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    key: str,
    name: str,
    description: str,
    user: User,
) -> Project:
    role = await _workspace_role(session, workspace_id, user)
    if role is not WorkspaceRole.OWNER:
        raise ForbiddenError("Only the workspace owner can create projects")
    project = Project(
        workspace_id=workspace_id, key=key, name=name, description=description, created_by=user.id
    )
    session.add(project)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(f"A project with key {key} already exists here") from exc
    session.add(ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.MANAGER))
    await session.commit()
    logger.info(
        "audit.project.created",
        extra=log_fields(actor=user.id, workspace_id=workspace_id, project_id=project.id),
    )
    return project


async def list_projects(
    session: AsyncSession, workspace_id: uuid.UUID, user: User
) -> list[tuple[Project, ProjectRole]]:
    await _workspace_role(session, workspace_id, user)
    rows = await session.execute(
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(Project.workspace_id == workspace_id, ProjectMember.user_id == user.id)
        .order_by(Project.name)
    )
    return [(p, role) for p, role in rows]


async def list_members(
    session: AsyncSession, project_id: uuid.UUID, user: User
) -> list[tuple[User, ProjectRole]]:
    await access.project_role(session, project_id, user)
    rows = await session.execute(
        select(User, ProjectMember.role)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .where(ProjectMember.project_id == project_id)
        .order_by(User.display_name)
    )
    return [(u, role) for u, role in rows]


async def add_member(
    session: AsyncSession, project_id: uuid.UUID, *, email: str, role: ProjectRole, actor: User
) -> User:
    """Adds an existing, verified account. Invitations for new people come with milestone 3."""
    project = await access.get_project(session, project_id, actor)
    await access.require_manager(session, project_id, actor)
    member = await session.scalar(
        select(User).where(
            User.email == normalize_email(email),
            User.email_verified_at.is_not(None),
            User.is_active,
        )
    )
    if member is None:
        raise NotFoundError("No verified account uses that email")

    # Joining a project means joining its workspace; keep an existing role there.
    await session.execute(
        insert(WorkspaceMember)
        .values(workspace_id=project.workspace_id, user_id=member.id, role=WorkspaceRole.MEMBER)
        .on_conflict_do_nothing()
    )
    session.add(ProjectMember(project_id=project_id, user_id=member.id, role=role))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("That person is already in the project") from exc
    logger.info(
        "audit.project.member_added",
        extra=log_fields(actor=actor.id, project_id=project_id, user_id=member.id, role=role.value),
    )
    return member


async def change_role(
    session: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role: ProjectRole,
    actor: User,
) -> None:
    await access.require_manager(session, project_id, actor)
    membership = await _membership(session, project_id, user_id)
    before = membership.role
    if before is ProjectRole.MANAGER and role is not ProjectRole.MANAGER:
        await _keep_one_manager(session, project_id)
    membership.role = role
    await session.commit()
    logger.info(
        "audit.project.role_changed",
        extra=log_fields(
            actor=actor.id,
            project_id=project_id,
            user_id=user_id,
            before=before.value,
            after=role.value,
        ),
    )


async def remove_member(
    session: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, actor: User
) -> None:
    await access.require_manager(session, project_id, actor)
    membership = await _membership(session, project_id, user_id)
    if membership.role is ProjectRole.MANAGER:
        await _keep_one_manager(session, project_id)
    await session.delete(membership)
    await session.commit()
    logger.info(
        "audit.project.member_removed",
        extra=log_fields(actor=actor.id, project_id=project_id, user_id=user_id),
    )


async def _workspace_role(
    session: AsyncSession, workspace_id: uuid.UUID, user: User
) -> WorkspaceRole:
    role = await session.scalar(
        select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id
        )
    )
    if role is None:
        raise NotFoundError("Workspace not found")
    return role


async def _membership(
    session: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> ProjectMember:
    membership = await session.get(ProjectMember, (project_id, user_id))
    if membership is None:
        raise NotFoundError("That person is not in the project")
    return membership


async def _keep_one_manager(session: AsyncSession, project_id: uuid.UUID) -> None:
    managers = await session.scalar(
        select(func.count()).where(
            ProjectMember.project_id == project_id, ProjectMember.role == ProjectRole.MANAGER
        )
    )
    if (managers or 0) <= 1:
        raise InvalidRequestError("A project needs at least one manager")
