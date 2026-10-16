import hmac
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError
from app.core.logging import log_fields
from app.core.security import hash_token, new_token
from app.db.models import OAuthIdentity, OAuthState, User
from app.services import rate_limit
from app.services.auth import create_session, normalize_email
from app.services.google import GoogleClient, GoogleIdentity, GoogleSignInError, pkce_challenge

logger = logging.getLogger(__name__)

PROVIDER = "google"
STATE_TTL = timedelta(minutes=10)


async def start(session: AsyncSession, google: GoogleClient) -> tuple[str, str]:
    """Returns Google's sign-in URL and the state to bind to this browser in a cookie."""
    state, verifier, nonce = new_token(), new_token(), new_token()
    session.add(
        OAuthState(
            state_hash=hash_token(state),
            code_verifier=verifier,
            nonce=nonce,
            expires_at=datetime.now(UTC) + STATE_TTL,
        )
    )
    await session.commit()
    url = google.authorization_url(
        state=state, nonce=nonce, code_challenge=pkce_challenge(verifier)
    )
    return url, state


async def finish(
    session: AsyncSession,
    google: GoogleClient,
    *,
    code: str,
    state: str,
    browser_state: str | None,
    ip: str,
) -> tuple[User, str]:
    """Returns the user and a new session token. Raises UnauthorizedError on anything odd."""
    await rate_limit.hit(session, f"google:ip:{ip}", limit=30, window=timedelta(minutes=15))
    # The state must come back to the same browser that started: stops login CSRF, where an
    # attacker makes you sign in to *their* account.
    if browser_state is None or not hmac.compare_digest(browser_state, state):
        raise _failed("state_mismatch")
    stored = (
        await session.execute(
            delete(OAuthState)
            .where(
                OAuthState.state_hash == hash_token(state),
                OAuthState.expires_at > datetime.now(UTC),
            )
            .returning(OAuthState.code_verifier, OAuthState.nonce)
        )
    ).first()
    await session.commit()  # used up, even if the rest fails
    if stored is None:
        raise _failed("state_unknown_or_expired")

    verifier, nonce = stored
    try:
        identity = await google.identity_from_code(code=code, code_verifier=verifier, nonce=nonce)
    except GoogleSignInError as exc:
        logger.warning("audit.auth.google_failed", extra=log_fields(reason=str(exc)))
        raise UnauthorizedError("Google sign-in failed") from exc
    if not identity.email_verified or not identity.email:
        raise _failed("email_not_verified_by_google")

    user = await _user_for(session, identity)
    if not user.is_active:
        raise _failed("inactive")
    token = await create_session(session, user)
    await session.commit()
    logger.info("audit.auth.signed_in", extra=log_fields(user_id=user.id, method=PROVIDER))
    return user, token


async def _user_for(session: AsyncSession, identity: GoogleIdentity) -> User:
    linked = await session.scalar(
        select(User)
        .join(OAuthIdentity, OAuthIdentity.user_id == User.id)
        .where(OAuthIdentity.provider == PROVIDER, OAuthIdentity.subject == identity.subject)
    )
    if linked is not None:
        return linked

    now = datetime.now(UTC)
    email = normalize_email(identity.email)
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        name = (identity.name or email.split("@")[0])[:100]
        user = User(email=email, display_name=name, email_verified_at=now)
        session.add(user)
        await session.flush()
        logger.info("audit.auth.signed_up", extra=log_fields(user_id=user.id, method=PROVIDER))
    elif user.email_verified_at is None:
        # Someone signed up with this address but never proved they own it. Google just proved
        # this person does, so the unproven password (maybe an attacker's) is dropped.
        user.password_hash = None
        user.email_verified_at = now
        logger.warning("audit.auth.unverified_password_cleared", extra=log_fields(user_id=user.id))

    session.add(OAuthIdentity(provider=PROVIDER, subject=identity.subject, user_id=user.id))
    logger.info("audit.auth.google_linked", extra=log_fields(user_id=user.id))
    return user


def _failed(reason: str) -> UnauthorizedError:
    logger.warning("audit.auth.google_failed", extra=log_fields(reason=reason))
    return UnauthorizedError("Google sign-in failed")
