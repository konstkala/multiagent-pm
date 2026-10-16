import hashlib
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import (
    FileTooLargeError,
    ForbiddenError,
    InvalidRequestError,
    NotFoundError,
    StorageUnavailableError,
)
from app.core.logging import log_fields
from app.db.models import ProjectRole, TicketAttachment, User
from app.services import access
from app.services.file_types import clean_filename, detect_content_type
from app.services.storage import Storage, StorageError
from app.services.tickets import get_ticket

logger = logging.getLogger(__name__)

AttachmentWithUploader = tuple[TicketAttachment, str | None]


async def list_attachments(
    session: AsyncSession, ticket_id: uuid.UUID, user: User
) -> list[AttachmentWithUploader]:
    await get_ticket(session, ticket_id, user)
    rows = await session.execute(
        select(TicketAttachment, User.display_name)
        .outerjoin(User, User.id == TicketAttachment.uploader_id)
        .where(TicketAttachment.ticket_id == ticket_id)
        .order_by(TicketAttachment.created_at)
    )
    return [(attachment, name) for attachment, name in rows]


async def upload(
    session: AsyncSession,
    storage: Storage,
    *,
    ticket_id: uuid.UUID,
    filename: str | None,
    data: bytes,
    actor: User,
) -> AttachmentWithUploader:
    ticket = await get_ticket(session, ticket_id, actor)  # any project member may attach
    if not data:
        raise InvalidRequestError("The file is empty")
    if len(data) > settings.attachment_max_bytes:
        raise FileTooLargeError(f"Files can be at most {settings.attachment_max_bytes // 2**20} MB")
    name = clean_filename(filename)
    content_type = detect_content_type(name, data)
    # Random key: the name is never part of the storage path, so it can't escape or collide.
    key = f"tickets/{ticket.id}/{uuid.uuid4().hex}"

    try:
        await storage.put(key, data, content_type)
    except StorageError as exc:
        logger.exception("storage.put_failed", extra=log_fields(ticket_id=ticket.id))
        raise StorageUnavailableError("File storage is unavailable. Try again shortly.") from exc
    attachment = TicketAttachment(
        ticket_id=ticket.id,
        uploader_id=actor.id,
        filename=name,
        content_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_key=key,
    )
    session.add(attachment)
    try:
        await session.commit()
    except Exception:
        await _delete_quietly(storage, key)  # don't leave an object nothing points to
        raise
    await session.refresh(attachment)
    logger.info(
        "audit.attachment.uploaded",
        extra=log_fields(
            actor=actor.id,
            ticket_id=ticket.id,
            attachment_id=attachment.id,
            content_type=content_type,
            size_bytes=len(data),
        ),
    )
    return attachment, actor.display_name


async def download(
    session: AsyncSession, storage: Storage, attachment_id: uuid.UUID, user: User
) -> tuple[TicketAttachment, bytes]:
    attachment = await _attachment_for(session, attachment_id, user)
    try:
        data = await storage.get(attachment.storage_key)
    except StorageError as exc:
        logger.exception("storage.get_failed", extra=log_fields(attachment_id=attachment.id))
        raise StorageUnavailableError("File storage is unavailable. Try again shortly.") from exc
    return attachment, data


async def delete(
    session: AsyncSession, storage: Storage, attachment_id: uuid.UUID, actor: User
) -> None:
    attachment = await _attachment_for(session, attachment_id, actor)
    if attachment.uploader_id != actor.id:
        ticket = await get_ticket(session, attachment.ticket_id, actor)
        if await access.project_role(session, ticket.project_id, actor) is not ProjectRole.MANAGER:
            raise ForbiddenError("You can only delete files you uploaded")
    key = attachment.storage_key
    await session.delete(attachment)
    await session.commit()
    await _delete_quietly(storage, key)
    logger.info(
        "audit.attachment.deleted", extra=log_fields(actor=actor.id, attachment_id=attachment_id)
    )


async def _attachment_for(
    session: AsyncSession, attachment_id: uuid.UUID, user: User
) -> TicketAttachment:
    attachment = await session.get(TicketAttachment, attachment_id)
    if attachment is None:
        raise NotFoundError("File not found")
    try:
        await get_ticket(session, attachment.ticket_id, user)
    except NotFoundError as exc:  # files in projects you can't see don't exist either
        raise NotFoundError("File not found") from exc
    return attachment


async def _delete_quietly(storage: Storage, key: str) -> None:
    try:
        await storage.delete(key)
    except StorageError:
        # The row is gone, so nobody can reach the file; a cleanup job can remove it later.
        logger.exception("storage.orphan_object", extra=log_fields(storage_key=key))
