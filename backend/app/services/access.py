"""Who may touch what. Every service that reads project data goes through here."""

import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.db.models import Project, ProjectMember, ProjectRole, User


async def project_role(session: AsyncSession, project_id: uuid.UUID, user: User) -> ProjectRole:
    """404, not 403, for outsiders: 'forbidden' would confirm the project exists."""
    role = await session.scalar(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user.id
        )
    )
    if role is None:
        raise NotFoundError("Project not found")
    return role


async def require_manager(session: AsyncSession, project_id: uuid.UUID, user: User) -> None:
    if await project_role(session, project_id, user) is not ProjectRole.MANAGER:
        raise ForbiddenError("Only project managers can do this")


async def get_project(session: AsyncSession, project_id: uuid.UUID, user: User) -> Project:
    await project_role(session, project_id, user)
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    return project


def member_projects(user: User) -> Select[uuid.UUID]:
    """Project ids the user belongs to, for use inside WHERE clauses."""
    return select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
