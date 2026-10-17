import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import exists, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, InvalidRequestError, NotFoundError
from app.core.logging import log_fields
from app.core.security import hash_token, new_token
from app.db.models import (
    Project,
    ProjectInvitation,
    ProjectMember,
    ProjectRole,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)
from app.services import access, rate_limit
from app.services.auth import normalize_email
from app.services.email import EmailSender, invitation_email, send_safely

logger = logging.getLogger(__name__)

INVITATION_TTL = timedelta(days=7)
_INVALID = "This invitation is invalid or has expired. Ask for a new one."

Status = Literal["pending", "accepted", "revoked", "expired"]


@dataclass(frozen=True)
class InvitationPreview:
    """What the invite page shows. Only the token holder (the invited inbox) can see it."""

    project_id: uuid.UUID
    project_name: str
    project_key: str
    workspace_name: str
    inviter_name: str | None
    email: str
    role: ProjectRole
    status: Status


async def invite(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    email: str,
    role: ProjectRole,
    actor: User,
    mailer: EmailSender,
) -> ProjectInvitation:
    project = await access.get_project(session, project_id, actor)
    await access.require_manager(session, project_id, actor)
    await rate_limit.hit(session, f"invite:user:{actor.id}", limit=50, window=timedelta(hours=1))
    email = normalize_email(email)
    if await _is_member(session, project_id, email):
        raise ConflictError("That person is already in the project")

    # Re-inviting replaces the open invitation: only the newest link works.
    now = datetime.now(UTC)
    await session.execute(
        update(ProjectInvitation)
        .where(
            ProjectInvitation.project_id == project_id,
            ProjectInvitation.email == email,
            ProjectInvitation.accepted_at.is_(None),
            ProjectInvitation.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    token = new_token()
    invitation = ProjectInvitation(
        project_id=project_id,
        email=email,
        role=role,
        token_hash=hash_token(token),
        invited_by=actor.id,
        expires_at=now + INVITATION_TTL,
    )
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)
    logger.info(
        "audit.invitation.created",
        extra=log_fields(
            actor=actor.id, project_id=project_id, invitation_id=invitation.id, role=role.value
        ),
    )
    await send_safely(mailer, invitation_email(email, actor.display_name, project.name, token))
    return invitation


async def list_pending(
    session: AsyncSession, project_id: uuid.UUID, actor: User
) -> list[tuple[ProjectInvitation, str | None]]:
    await access.require_manager(session, project_id, actor)
    rows = await session.execute(
        select(ProjectInvitation, User.display_name)
        .outerjoin(User, User.id == ProjectInvitation.invited_by)
        .where(
            ProjectInvitation.project_id == project_id,
            ProjectInvitation.accepted_at.is_(None),
            ProjectInvitation.revoked_at.is_(None),
            ProjectInvitation.expires_at > datetime.now(UTC),
        )
        .order_by(ProjectInvitation.created_at.desc())
    )
    return [(invitation, name) for invitation, name in rows]


async def revoke(session: AsyncSession, invitation_id: uuid.UUID, actor: User) -> None:
    invitation = await session.get(ProjectInvitation, invitation_id)
    if invitation is None:
        raise NotFoundError("Invitation not found")
    try:
        await access.require_manager(session, invitation.project_id, actor)
    except NotFoundError as exc:
        raise NotFoundError("Invitation not found") from exc
    if invitation.accepted_at is None and invitation.revoked_at is None:
        invitation.revoked_at = datetime.now(UTC)
        await session.commit()
        logger.info(
            "audit.invitation.revoked",
            extra=log_fields(actor=actor.id, invitation_id=invitation.id),
        )


async def preview(session: AsyncSession, token: str) -> InvitationPreview:
    row = (
        await session.execute(
            select(ProjectInvitation, Project, Workspace, User.display_name)
            .join(Project, Project.id == ProjectInvitation.project_id)
            .join(Workspace, Workspace.id == Project.workspace_id)
            .outerjoin(User, User.id == ProjectInvitation.invited_by)
            .where(ProjectInvitation.token_hash == hash_token(token))
        )
    ).first()
    if row is None:
        raise InvalidRequestError(_INVALID)
    invitation, project, workspace, inviter = row
    return InvitationPreview(
        project_id=project.id,
        project_name=project.name,
        project_key=project.key,
        workspace_name=workspace.name,
        inviter_name=inviter,
        email=invitation.email,
        role=invitation.role,
        status=_status(invitation),
    )


async def accept(session: AsyncSession, token: str, user: User) -> uuid.UUID:
    """Joins the signed-in user to the project. Returns the project id."""
    invitation = await session.scalar(
        select(ProjectInvitation)
        .where(ProjectInvitation.token_hash == hash_token(token))
        .with_for_update()  # two clicks can't both accept
    )
    if invitation is None or _status(invitation) != "pending":
        raise InvalidRequestError(_INVALID)
    # A forwarded link must not let a different account in.
    if user.email != invitation.email or user.email_verified_at is None:
        logger.warning(
            "audit.invitation.wrong_account",
            extra=log_fields(user_id=user.id, invitation_id=invitation.id),
        )
        raise ForbiddenError(
            "This invitation was sent to a different email address. "
            "Sign in with that address to accept it."
        )

    project = await session.get(Project, invitation.project_id)
    if project is None:
        raise InvalidRequestError(_INVALID)
    await session.execute(
        insert(WorkspaceMember)
        .values(workspace_id=project.workspace_id, user_id=user.id, role=WorkspaceRole.MEMBER)
        .on_conflict_do_nothing()
    )
    await session.execute(
        insert(ProjectMember)
        .values(project_id=project.id, user_id=user.id, role=invitation.role)
        .on_conflict_do_nothing()  # already a member: still mark the invitation as used
    )
    invitation.accepted_at = datetime.now(UTC)
    invitation.accepted_by = user.id
    await session.commit()
    logger.info(
        "audit.invitation.accepted",
        extra=log_fields(user_id=user.id, invitation_id=invitation.id, project_id=project.id),
    )
    return project.id


async def _is_member(session: AsyncSession, project_id: uuid.UUID, email: str) -> bool:
    return bool(
        await session.scalar(
            select(
                exists()
                .where(ProjectMember.project_id == project_id)
                .where(ProjectMember.user_id == User.id)
                .where(User.email == email)
            )
        )
    )


def _status(invitation: ProjectInvitation) -> Status:
    if invitation.accepted_at is not None:
        return "accepted"
    if invitation.revoked_at is not None:
        return "revoked"
    if invitation.expires_at <= datetime.now(UTC):
        return "expired"
    return "pending"
