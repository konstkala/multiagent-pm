from fastapi import APIRouter, Request, Response, status

from app.api.deps import SESSION_COOKIE, CurrentUser, MailerDep, SessionDep, client_ip
from app.core.config import settings
from app.schemas.auth import (
    EmailRequest,
    MessageResponse,
    ResetPasswordRequest,
    SignInRequest,
    SignUpRequest,
    TokenRequest,
    UserRead,
)
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])

_CHECK_INBOX = MessageResponse(
    message="If the address can receive email, a message is on its way. Check your inbox."
)


@router.post("/sign-up", status_code=status.HTTP_202_ACCEPTED)
async def sign_up(
    data: SignUpRequest, request: Request, session: SessionDep, mailer: MailerDep
) -> MessageResponse:
    await auth.sign_up(
        session,
        email=data.email,
        password=data.password,
        display_name=data.display_name,
        ip=client_ip(request),
        mailer=mailer,
    )
    return _CHECK_INBOX


@router.post("/verify-email")
async def verify_email(data: TokenRequest, session: SessionDep) -> MessageResponse:
    await auth.verify_email(session, data.token)
    return MessageResponse(message="Email confirmed. You can sign in now.")


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    data: EmailRequest, request: Request, session: SessionDep, mailer: MailerDep
) -> MessageResponse:
    await auth.resend_verification(session, email=data.email, ip=client_ip(request), mailer=mailer)
    return _CHECK_INBOX


@router.post("/sign-in")
async def sign_in(
    data: SignInRequest, request: Request, response: Response, session: SessionDep
) -> UserRead:
    user, token = await auth.sign_in(
        session, email=data.email, password=data.password, ip=client_ip(request)
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,  # page scripts can't read it, so XSS can't steal it
        secure=settings.cookie_secure,
        samesite="lax",  # not sent on cross-site POSTs
        path="/",
    )
    return UserRead.model_validate(user)


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(request: Request, response: Response, session: SessionDep) -> None:
    if token := request.cookies.get(SESSION_COOKIE):
        await auth.sign_out(session, token)
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, secure=settings.cookie_secure, samesite="lax", path="/"
    )


@router.get("/me")
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    data: EmailRequest, request: Request, session: SessionDep, mailer: MailerDep
) -> MessageResponse:
    await auth.request_password_reset(
        session, email=data.email, ip=client_ip(request), mailer=mailer
    )
    return _CHECK_INBOX


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, session: SessionDep) -> MessageResponse:
    await auth.reset_password(session, token=data.token, password=data.password)
    return MessageResponse(message="Password changed. Sign in with your new password.")
