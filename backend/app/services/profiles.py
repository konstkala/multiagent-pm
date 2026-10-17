"""Employee profiles: what each person brings to a workspace."""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging import log_fields
from app.db.models import (
    EmployeeProfile,
    ProfileSkill,
    Project,
    ProjectMember,
    ProjectRole,
    User,
    WorkspaceMember,
    WorkspaceRole,
)
from app.schemas.profiles import ProfileWrite

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Profile:
    user: User
    profile: EmployeeProfile | None
    skills: list[ProfileSkill]


@dataclass(frozen=True)
class Person:
    user: User
    workspace_role: WorkspaceRole
    headline: str
    skill_count: int


async def can_manage_people(session: AsyncSession, workspace_id: uuid.UUID, user: User) -> bool:
    """The workspace owner, or a manager of any project in the workspace."""
    owner = exists().where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user.id,
        WorkspaceMember.role == WorkspaceRole.OWNER,
    )
    manager = (
        exists()
        .where(ProjectMember.project_id == Project.id)
        .where(
            Project.workspace_id == workspace_id,
            ProjectMember.user_id == user.id,
            ProjectMember.role == ProjectRole.MANAGER,
        )
    )
    return bool(await session.scalar(select(owner | manager)))


async def require_people_manager(
    session: AsyncSession, workspace_id: uuid.UUID, user: User
) -> None:
    if not await _workspace_role(session, workspace_id, user.id):
        raise NotFoundError("Workspace not found")
    if not await can_manage_people(session, workspace_id, user):
        raise ForbiddenError("Only managers can manage people's profiles")


async def list_people(session: AsyncSession, workspace_id: uuid.UUID, actor: User) -> list[Person]:
    await require_people_manager(session, workspace_id, actor)
    skill_count = (
        select(func.count())
        .where(ProfileSkill.workspace_id == workspace_id, ProfileSkill.user_id == User.id)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(User, WorkspaceMember.role, EmployeeProfile.headline, skill_count)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .outerjoin(
            EmployeeProfile,
            (EmployeeProfile.user_id == User.id) & (EmployeeProfile.workspace_id == workspace_id),
        )
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(User.display_name)
    )
    return [
        Person(user=user, workspace_role=role, headline=headline or "", skill_count=count)
        for user, role, headline, count in rows
    ]


async def get_profile(
    session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID, actor: User
) -> Profile:
    """People see their own profile; managers see everyone's in the workspace."""
    if actor.id != user_id:
        await require_people_manager(session, workspace_id, actor)
    elif not await _workspace_role(session, workspace_id, actor.id):
        raise NotFoundError("Workspace not found")
    user = await _member(session, workspace_id, user_id)
    profile = await session.get(EmployeeProfile, (workspace_id, user_id))
    skills = await session.scalars(
        select(ProfileSkill)
        .where(ProfileSkill.workspace_id == workspace_id, ProfileSkill.user_id == user_id)
        .order_by(ProfileSkill.level.desc(), ProfileSkill.name)
    )
    return Profile(user=user, profile=profile, skills=list(skills))


async def save_profile(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    data: ProfileWrite,
    actor: User,
    *,
    commit: bool = True,
) -> None:
    """Replaces the profile and its skills. `commit=False` lets a caller bundle it."""
    await require_people_manager(session, workspace_id, actor)
    await _member(session, workspace_id, user_id)
    values = {
        "headline": data.headline,
        "summary": data.summary,
        "years_experience": data.years_experience,
        "updated_by": actor.id,
        "updated_at": func.now(),
    }
    await session.execute(
        insert(EmployeeProfile)
        .values(workspace_id=workspace_id, user_id=user_id, **values)
        .on_conflict_do_update(index_elements=["workspace_id", "user_id"], set_=values)
    )
    await session.execute(
        delete(ProfileSkill).where(
            ProfileSkill.workspace_id == workspace_id, ProfileSkill.user_id == user_id
        )
    )
    session.add_all(
        ProfileSkill(workspace_id=workspace_id, user_id=user_id, name=s.name, level=s.level)
        for s in data.skills
    )
    if commit:
        await session.commit()
    # Counts only: skills and wording are personal data.
    logger.info(
        "audit.profile.saved",
        extra=log_fields(
            actor=actor.id,
            workspace_id=workspace_id,
            user_id=user_id,
            skill_count=len(data.skills),
        ),
    )


async def _workspace_role(
    session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceRole | None:
    return await session.scalar(
        select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id
        )
    )


async def _member(session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = await session.scalar(
        select(User)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == workspace_id, User.id == user_id)
    )
    if user is None:
        raise NotFoundError("That person isn't in this workspace")
    return user
