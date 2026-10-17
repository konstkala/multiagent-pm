import uuid
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, MailerDep, SessionDep
from app.api.errors import ErrorResponse
from app.db.models import ProjectInvitation
from app.schemas.workspaces import (
    AcceptedInvitation,
    InvitationCreate,
    InvitationPreviewRead,
    InvitationRead,
    InvitationToken,
)
from app.services import invitations

router = APIRouter(tags=["invitations"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (403, 404, 409, 422, 429)
}


def _read(invitation: ProjectInvitation, inviter: str | None) -> InvitationRead:
    return InvitationRead(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        invited_by_name=inviter,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@router.post(
    "/projects/{project_id}/invitations", status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
async def invite(
    project_id: uuid.UUID,
    data: InvitationCreate,
    session: SessionDep,
    user: CurrentUser,
    mailer: MailerDep,
) -> InvitationRead:
    invitation = await invitations.invite(
        session, project_id, email=data.email, role=data.role, actor=user, mailer=mailer
    )
    return _read(invitation, user.display_name)


@router.get("/projects/{project_id}/invitations", responses=_ERRORS)
async def list_invitations(
    project_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[InvitationRead]:
    pending = await invitations.list_pending(session, project_id, user)
    return [_read(invitation, inviter) for invitation, inviter in pending]


@router.delete(
    "/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS
)
async def revoke_invitation(
    invitation_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    await invitations.revoke(session, invitation_id, user)


# POST, not GET: the token stays out of URLs, browser history and access logs.
@router.post("/invitations/preview", responses=_ERRORS)
async def preview_invitation(data: InvitationToken, session: SessionDep) -> InvitationPreviewRead:
    return InvitationPreviewRead(**asdict(await invitations.preview(session, data.token)))


@router.post("/invitations/accept", responses=_ERRORS)
async def accept_invitation(
    data: InvitationToken, session: SessionDep, user: CurrentUser
) -> AcceptedInvitation:
    project_id = await invitations.accept(session, data.token, user)
    return AcceptedInvitation(project_id=project_id)
