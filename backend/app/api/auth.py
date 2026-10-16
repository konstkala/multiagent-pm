from fastapi import APIRouter, Request, Response, status
from fastapi.responses import RedirectResponse

from app.api.deps import SESSION_COOKIE, CurrentUser, GoogleDep, MailerDep, SessionDep, client_ip
from app.core.config import settings
from app.core.errors import DomainError, NotFoundError
from app.schemas.auth import (
    EmailRequest,
    MessageResponse,
    ProvidersResponse,
    ResetPasswordRequest,
    SignInRequest,
    SignUpRequest,
    TokenRequest,
    UserRead,
)
from app.services import auth, google_sign_in

router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_STATE_COOKIE = "pm_oauth_state"

_CHECK_INBOX = MessageResponse(
    message="If the address can receive email, a message is on its way. Check your inbox."
)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,  # page scripts can't read it, so XSS can't steal it
        secure=settings.cookie_secure,
        samesite="lax",  # not sent on cross-site POSTs
        path="/",
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
    _set_session_cookie(response, token)
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


@router.get("/providers")
async def providers(google: GoogleDep) -> ProvidersResponse:
    """Which external sign-in buttons the frontend should show."""
    return ProvidersResponse(google=google is not None)


@router.get("/google/start", status_code=status.HTTP_302_FOUND)
async def google_start(session: SessionDep, google: GoogleDep) -> RedirectResponse:
    if google is None:
        raise NotFoundError("Google sign-in isn't set up")
    url, state = await google_sign_in.start(session, google)
    response = RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=int(google_sign_in.STATE_TTL.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",  # still sent when Google redirects the browser back (a top-level GET)
        path="/",
    )
    return response


@router.get("/google/callback", status_code=status.HTTP_302_FOUND)
async def google_callback(
    request: Request,
    session: SessionDep,
    google: GoogleDep,
    code: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    """Google sends the browser here. We always answer with a redirect back to the app."""
    failed = RedirectResponse(
        f"{settings.app_base_url}/sign-in?error=google", status_code=status.HTTP_302_FOUND
    )
    failed.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    if google is None or code is None or state is None:  # e.g. the user pressed Cancel
        return failed
    try:
        _, token = await google_sign_in.finish(
            session,
            google,
            code=code,
            state=state,
            browser_state=request.cookies.get(OAUTH_STATE_COOKIE),
            ip=client_ip(request),
        )
    except DomainError:  # failed checks, rate limits: the browser goes back to sign-in
        return failed
    response = RedirectResponse(
        f"{settings.app_base_url}/projects", status_code=status.HTTP_302_FOUND
    )
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    _set_session_cookie(response, token)
    return response
