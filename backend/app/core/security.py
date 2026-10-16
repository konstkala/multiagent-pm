import asyncio
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# argon2id with the library's defaults, which follow the OWASP recommendation.
_hasher = PasswordHasher()
# Checked when the email is unknown, so a wrong email takes as long as a wrong password.
_DUMMY_HASH = _hasher.hash("equalise-timing-for-unknown-users")


async def hash_password(password: str) -> str:
    # ~50 ms of CPU on purpose; a thread keeps the event loop serving other requests.
    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password_hash: str | None, password: str) -> bool:
    def check() -> bool:
        try:
            matched = _hasher.verify(password_hash or _DUMMY_HASH, password)
        except (VerificationError, InvalidHashError):
            return False
        return matched and password_hash is not None

    return await asyncio.to_thread(check)


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Tokens are long and random, so a fast hash is enough (unlike passwords)."""
    return hashlib.sha256(token.encode()).hexdigest()
