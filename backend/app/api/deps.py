from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError
from app.db.models import User
from app.db.session import get_session
from app.services import auth
from app.services.email import EmailSender, get_email_sender
from app.services.google import GoogleClient, get_google_client

SESSION_COOKIE = "pm_session"

SessionDep = Annotated[AsyncSession, Depends(get_session)]
MailerDep = Annotated[EmailSender, Depends(get_email_sender)]
GoogleDep = Annotated[GoogleClient | None, Depends(get_google_client)]


def client_ip(request: Request) -> str:
    # Behind a proxy this needs the proxy's forwarded header (uvicorn --proxy-headers).
    return request.client.host if request.client else "unknown"


async def current_user(request: Request, session: SessionDep) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    user = await auth.user_for_session(session, token) if token else None
    if user is None:
        raise UnauthorizedError("Sign in to continue")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
