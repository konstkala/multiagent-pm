"""Google sign-in with OpenID Connect: authorization code flow + PKCE + nonce."""

import asyncio
import base64
import hashlib
import hmac
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import settings

# From https://accounts.google.com/.well-known/openid-configuration
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")


class GoogleSignInError(Exception):
    """Anything that makes us distrust the response. Details are logged, never shown."""


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str  # Google's stable account id; emails can change
    email: str
    email_verified: bool
    name: str | None


class GoogleClient(Protocol):
    def authorization_url(self, *, state: str, nonce: str, code_challenge: str) -> str: ...

    async def identity_from_code(
        self, *, code: str, code_verifier: str, nonce: str
    ) -> GoogleIdentity: ...


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def verify_id_token(id_token: str, key: Any, *, client_id: str, nonce: str) -> dict[str, Any]:
    """Signature, issuer, audience, expiry and nonce. Anything off raises GoogleSignInError."""
    try:
        claims: dict[str, Any] = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=ISSUERS,
            leeway=30,  # small clock differences between servers
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise GoogleSignInError(f"ID token rejected: {type(exc).__name__}") from exc
    # The nonce ties the token to the attempt we started, so a stolen token can't be replayed.
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise GoogleSignInError("ID token nonce mismatch")
    return claims


class GoogleOidcClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._keys = jwt.PyJWKClient(JWKS_URL, cache_keys=True)  # Google rotates its keys

    def authorization_url(self, *, state: str, nonce: str, code_challenge: str) -> str:
        query = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        return f"{AUTH_URL}?{urlencode(query)}"

    async def identity_from_code(
        self, *, code: str, code_verifier: str, nonce: str
    ) -> GoogleIdentity:
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                response = await http.post(
                    TOKEN_URL,
                    data={
                        "code": code,
                        "code_verifier": code_verifier,
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "redirect_uri": self._redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
                response.raise_for_status()
            id_token = str(response.json()["id_token"])
            key = await asyncio.to_thread(self._keys.get_signing_key_from_jwt, id_token)
        except (httpx.HTTPError, KeyError, ValueError, jwt.PyJWTError) as exc:
            raise GoogleSignInError(f"token exchange failed: {type(exc).__name__}") from exc

        claims = verify_id_token(id_token, key.key, client_id=self._client_id, nonce=nonce)
        return GoogleIdentity(
            subject=str(claims["sub"]),
            email=str(claims.get("email", "")),
            email_verified=claims.get("email_verified") is True,
            name=claims.get("name"),
        )


@lru_cache(maxsize=1)
def get_google_client() -> GoogleClient | None:
    """None until a Google OAuth client is configured; the sign-in button stays hidden."""
    secret = settings.google_client_secret
    if not settings.google_client_id or secret is None:
        return None
    return GoogleOidcClient(
        settings.google_client_id,
        secret.get_secret_value(),
        f"{settings.public_api_url}/auth/google/callback",
    )
