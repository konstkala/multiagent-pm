import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, UploadFile, status

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ErrorResponse
from app.core.config import settings
from app.db.models import CvImport
from app.schemas.profiles import (
    CvImportRead,
    PersonRead,
    ProfileDraftRead,
    ProfileRead,
    ProfileWrite,
    SkillRead,
)
from app.services import cv_imports, profiles
from app.services.storage import Storage, get_storage

router = APIRouter(tags=["people"])

StorageDep = Annotated[Storage, Depends(get_storage)]

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (403, 404, 409, 413, 422, 503)
}


def _profile(found: profiles.Profile) -> ProfileRead:
    return ProfileRead(
        user_id=found.user.id,
        display_name=found.user.display_name,
        email=found.user.email,
        headline=found.profile.headline if found.profile else "",
        summary=found.profile.summary if found.profile else "",
        years_experience=found.profile.years_experience if found.profile else None,
        skills=[SkillRead(name=s.name, level=s.level) for s in found.skills],
        updated_at=found.profile.updated_at if found.profile else None,
    )


def _import(cv_import: CvImport) -> CvImportRead:
    return CvImportRead(
        id=cv_import.id,
        workspace_id=cv_import.workspace_id,
        user_id=cv_import.user_id,
        status=cv_import.status,
        error_code=cv_import.error_code,
        draft=ProfileDraftRead.model_validate(cv_import.draft) if cv_import.draft else None,
        model=cv_import.model,
        cost_usd=cv_import.cost_usd,
        latency_ms=cv_import.latency_ms,
        created_at=cv_import.created_at,
        processed_at=cv_import.processed_at,
    )


@router.get("/workspaces/{workspace_id}/people", responses=_ERRORS)
async def list_people(
    workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[PersonRead]:
    return [
        PersonRead(
            user_id=p.user.id,
            display_name=p.user.display_name,
            email=p.user.email,
            workspace_role=p.workspace_role,
            headline=p.headline,
            skill_count=p.skill_count,
        )
        for p in await profiles.list_people(session, workspace_id, user)
    ]


@router.get("/workspaces/{workspace_id}/people/{user_id}/profile", responses=_ERRORS)
async def get_profile(
    workspace_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> ProfileRead:
    return _profile(await profiles.get_profile(session, workspace_id, user_id, user))


@router.put("/workspaces/{workspace_id}/people/{user_id}/profile", responses=_ERRORS)
async def save_profile(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    data: ProfileWrite,
    session: SessionDep,
    user: CurrentUser,
) -> ProfileRead:
    await profiles.save_profile(session, workspace_id, user_id, data, user)
    return _profile(await profiles.get_profile(session, workspace_id, user_id, user))


@router.post(
    "/workspaces/{workspace_id}/people/{user_id}/cv",
    status_code=status.HTTP_202_ACCEPTED,
    responses=_ERRORS,
)
async def import_cv(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    file: UploadFile,
    session: SessionDep,
    user: CurrentUser,
    storage: StorageDep,
) -> CvImportRead:
    """Accepted for processing: the agent runs in the background. Poll the import for the draft."""
    data = await file.read(settings.cv_max_bytes + 1)
    cv_import = await cv_imports.start(
        session, storage, workspace_id=workspace_id, user_id=user_id, data=data, actor=user
    )
    return _import(cv_import)


@router.get("/workspaces/{workspace_id}/cv-imports", responses=_ERRORS)
async def list_cv_imports(
    workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[CvImportRead]:
    return [_import(i) for i in await cv_imports.list_for_workspace(session, workspace_id, user)]


@router.get("/cv-imports/{import_id}", responses=_ERRORS)
async def get_cv_import(
    import_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> CvImportRead:
    return _import(await cv_imports.get(session, import_id, user))


@router.post("/cv-imports/{import_id}/approve", responses=_ERRORS)
async def approve_cv_import(
    import_id: uuid.UUID, data: ProfileWrite, session: SessionDep, user: CurrentUser
) -> CvImportRead:
    return _import(await cv_imports.approve(session, import_id, data, user))


@router.post("/cv-imports/{import_id}/reject", responses=_ERRORS)
async def reject_cv_import(
    import_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> CvImportRead:
    return _import(await cv_imports.reject(session, import_id, user))
