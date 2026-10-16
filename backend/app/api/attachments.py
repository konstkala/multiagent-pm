import uuid
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response, UploadFile, status

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ErrorResponse
from app.core.config import settings
from app.db.models import TicketAttachment
from app.schemas.tickets import AttachmentRead
from app.services import attachments
from app.services.file_types import IMAGE_TYPES
from app.services.storage import Storage, get_storage

router = APIRouter(tags=["attachments"])

StorageDep = Annotated[Storage, Depends(get_storage)]

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (403, 404, 413, 422, 503)
}


def _read(attachment: TicketAttachment, uploader_name: str | None) -> AttachmentRead:
    return AttachmentRead(
        id=attachment.id,
        ticket_id=attachment.ticket_id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        uploader_id=attachment.uploader_id,
        uploader_name=uploader_name,
        created_at=attachment.created_at,
    )


def _disposition(kind: str, filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode().replace('"', "") or "file"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


@router.get("/tickets/{ticket_id}/attachments", responses=_ERRORS)
async def list_attachments(
    ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[AttachmentRead]:
    rows = await attachments.list_attachments(session, ticket_id, user)
    return [_read(a, name) for a, name in rows]


@router.post(
    "/tickets/{ticket_id}/attachments", status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
async def upload_attachment(
    ticket_id: uuid.UUID,
    file: UploadFile,
    session: SessionDep,
    user: CurrentUser,
    storage: StorageDep,
) -> AttachmentRead:
    # Read one byte past the limit: enough to know it's too big without trusting headers.
    data = await file.read(settings.attachment_max_bytes + 1)
    attachment, name = await attachments.upload(
        session, storage, ticket_id=ticket_id, filename=file.filename, data=data, actor=user
    )
    return _read(attachment, name)


@router.get("/attachments/{attachment_id}/download", responses=_ERRORS)
async def download_attachment(
    attachment_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    storage: StorageDep,
    inline: bool = False,
) -> Response:
    attachment, data = await attachments.download(session, storage, attachment_id, user)
    # Only images may open in the browser; everything else downloads.
    kind = "inline" if inline and attachment.content_type in IMAGE_TYPES else "attachment"
    return Response(
        content=data,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": _disposition(kind, attachment.filename),
            "X-Content-Type-Options": "nosniff",
            # Even if a file is opened directly, no script in it may run.
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete(
    "/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS
)
async def delete_attachment(
    attachment_id: uuid.UUID, session: SessionDep, user: CurrentUser, storage: StorageDep
) -> None:
    await attachments.delete(session, storage, attachment_id, user)
