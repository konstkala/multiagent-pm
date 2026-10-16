import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import EmailNotVerifiedError, InvalidRequestError, UnauthorizedError
from app.core.logging import log_fields
from app.core.security import hash_password, hash_token, needs_rehash, new_token, verify_password
from app.db.models import EmailToken, EmailTokenPurpose, User, UserSession
from app.services import rate_limit
from app.services.email import (
    EmailSender,
    account_exists_email,
    reset_password_email,
    send_safely,
    verification_email,
)

logger = logging.getLogger(__name__)

VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(minutes=30)
_LAST_SEEN_EVERY = timedelta(hours=1)  # avoids a database write on every request

_QUARTER_HOUR = timedelta(minutes=15)
_HOUR = timedelta(hours=1)

_INVALID_LINK = "This link is invalid or has expired. Ask for a new one."


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _email_key(email: str) -> str:
    # Rate-limit keys are stored, so they hold a hash, never the address.
    return hash_token(email)[:32]


async def sign_up(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str,
    ip: str,
    mailer: EmailSender,
) -> None:
    """Same outcome for new and existing emails, so nobody can probe which emails have accounts."""
    await rate_limit.hit(session, f"sign_up:ip:{ip}", limit=10, window=_HOUR)
    email = normalize_email(email)
    if await _user_by_email(session, email) is not None:
        await send_safely(mailer, account_exists_email(email))
        return

    user = User(email=email, display_name=display_name, password_hash=await hash_password(password))
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:  # someone signed up with the same email a moment ago
        await session.rollback()
        return
    token = await _issue_email_token(session, user, EmailTokenPurpose.VERIFY_EMAIL, VERIFY_TTL)
    await session.commit()
    logger.info("audit.auth.signed_up", extra=log_fields(user_id=user.id))
    await send_safely(mailer, verification_email(email, token))


async def verify_email(session: AsyncSession, token: str) -> None:
    email_token, user = await _redeem_email_token(session, token, EmailTokenPurpose.VERIFY_EMAIL)
    if user.email_verified_at is None:
        user.email_verified_at = email_token.used_at
    await session.commit()
    logger.info("audit.auth.email_verified", extra=log_fields(user_id=user.id))


async def resend_verification(
    session: AsyncSession, *, email: str, ip: str, mailer: EmailSender
) -> None:
    email = normalize_email(email)
    await rate_limit.hit(session, f"resend:ip:{ip}", limit=10, window=_HOUR)
    await rate_limit.hit(session, f"resend:email:{_email_key(email)}", limit=3, window=_HOUR)
    user = await _user_by_email(session, email)
    if user is None or user.email_verified_at is not None or not user.is_active:
        return
    token = await _issue_email_token(session, user, EmailTokenPurpose.VERIFY_EMAIL, VERIFY_TTL)
    await session.commit()
    await send_safely(mailer, verification_email(email, token))


async def sign_in(session: AsyncSession, *, email: str, password: str, ip: str) -> tuple[User, str]:
    """Returns the user and a new session token for the cookie."""
    email = normalize_email(email)
    await rate_limit.hit(session, f"sign_in:ip:{ip}", limit=30, window=_QUARTER_HOUR)
    await rate_limit.hit(
        session, f"sign_in:email:{_email_key(email)}", limit=10, window=_QUARTER_HOUR
    )
    user = await _user_by_email(session, email)
    # Always verify, even for unknown emails, so response time doesn't reveal which exist.
    password_ok = await verify_password(user.password_hash if user else None, password)
    if user is None or not password_ok or not user.is_active:
        logger.warning(
            "audit.auth.sign_in_failed",
            extra=log_fields(user_id=user.id if user else None, reason=_failure(user, password_ok)),
        )
        raise UnauthorizedError("Incorrect email or password")
    if user.email_verified_at is None:
        raise EmailNotVerifiedError("Confirm your email address before signing in")

    assert user.password_hash is not None  # password_ok is False without one
    if needs_rehash(user.password_hash):
        user.password_hash = await hash_password(password)
    token = await _create_session(session, user)
    await session.commit()
    logger.info("audit.auth.signed_in", extra=log_fields(user_id=user.id))
    return user, token


async def sign_out(session: AsyncSession, token: str) -> None:
    result = await session.execute(
        delete(UserSession)
        .where(UserSession.token_hash == hash_token(token))
        .returning(UserSession.user_id)
    )
    user_id = result.scalar_one_or_none()
    await session.commit()
    if user_id is not None:
        logger.info("audit.auth.signed_out", extra=log_fields(user_id=user_id))


async def user_for_session(session: AsyncSession, token: str) -> User | None:
    now = datetime.now(UTC)
    row = (
        await session.execute(
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .where(
                UserSession.token_hash == hash_token(token),
                UserSession.expires_at > now,
                User.is_active,
            )
        )
    ).first()
    if row is None:
        return None
    user_session, user = row
    if now - user_session.last_seen_at > _LAST_SEEN_EVERY:
        user_session.last_seen_at = now
        await session.commit()
    return user


async def request_password_reset(
    session: AsyncSession, *, email: str, ip: str, mailer: EmailSender
) -> None:
    """Same response whether or not the email has an account."""
    email = normalize_email(email)
    await rate_limit.hit(session, f"reset:ip:{ip}", limit=10, window=_HOUR)
    await rate_limit.hit(session, f"reset:email:{_email_key(email)}", limit=3, window=_HOUR)
    user = await _user_by_email(session, email)
    if user is None or not user.is_active:
        return
    # Only the newest link works.
    await session.execute(
        update(EmailToken)
        .where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == EmailTokenPurpose.RESET_PASSWORD,
            EmailToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(UTC))
    )
    token = await _issue_email_token(session, user, EmailTokenPurpose.RESET_PASSWORD, RESET_TTL)
    await session.commit()
    logger.info("audit.auth.password_reset_requested", extra=log_fields(user_id=user.id))
    await send_safely(mailer, reset_password_email(email, token))


async def reset_password(session: AsyncSession, *, token: str, password: str) -> None:
    email_token, user = await _redeem_email_token(session, token, EmailTokenPurpose.RESET_PASSWORD)
    user.password_hash = await hash_password(password)
    if user.email_verified_at is None:  # they just proved they read this inbox
        user.email_verified_at = email_token.used_at
    # Whoever knew the old password is signed out everywhere.
    await session.execute(delete(UserSession).where(UserSession.user_id == user.id))
    await session.commit()
    logger.info("audit.auth.password_reset", extra=log_fields(user_id=user.id))


async def _user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def _create_session(session: AsyncSession, user: User) -> str:
    token = new_token()
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.session_ttl_days),
        )
    )
    return token


async def _issue_email_token(
    session: AsyncSession, user: User, purpose: EmailTokenPurpose, ttl: timedelta
) -> str:
    token = new_token()
    session.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + ttl,
        )
    )
    await session.flush()
    return token


async def _redeem_email_token(
    session: AsyncSession, token: str, purpose: EmailTokenPurpose
) -> tuple[EmailToken, User]:
    now = datetime.now(UTC)
    # FOR UPDATE: two clicks on the same link can't both succeed.
    row = (
        await session.execute(
            select(EmailToken, User)
            .join(User, User.id == EmailToken.user_id)
            .where(
                EmailToken.token_hash == hash_token(token),
                EmailToken.purpose == purpose,
                EmailToken.used_at.is_(None),
                EmailToken.expires_at > now,
                User.is_active,
            )
            .with_for_update(of=EmailToken)
        )
    ).first()
    if row is None:
        logger.warning("audit.auth.invalid_email_token", extra=log_fields(purpose=purpose.value))
        raise InvalidRequestError(_INVALID_LINK)
    email_token, user = row
    email_token.used_at = now
    return email_token, user


def _failure(user: User | None, password_ok: bool) -> str:
    if user is None:
        return "unknown_email"
    if not user.is_active:
        return "inactive"
    return "wrong_password" if not password_ok else "unknown"
