import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services.google import GoogleSignInError, pkce_challenge, verify_id_token

CLIENT_ID = "client-123.apps.googleusercontent.com"
NONCE = "nonce-abc"
GOOGLE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def id_token(key: rsa.RSAPrivateKey = GOOGLE_KEY, **overrides: Any) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1234567890",
        "email": "ada@example.com",
        "email_verified": True,
        "iat": now,
        "exp": now + 600,
        "nonce": NONCE,
    } | overrides
    return jwt.encode(claims, key, algorithm="RS256")


def verify(token: str) -> dict[str, Any]:
    return verify_id_token(token, GOOGLE_KEY.public_key(), client_id=CLIENT_ID, nonce=NONCE)


def test_valid_token_returns_claims() -> None:
    assert verify(id_token())["sub"] == "1234567890"


def test_both_google_issuer_spellings_are_accepted() -> None:
    assert verify(id_token(iss="accounts.google.com"))["sub"] == "1234567890"


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(id_token(OTHER_KEY), id="signed by someone else"),
        pytest.param(id_token(aud="another-app"), id="issued for another app"),
        pytest.param(id_token(iss="https://evil.example"), id="wrong issuer"),
        pytest.param(id_token(exp=int(time.time()) - 3600), id="expired"),
        pytest.param(id_token(nonce="replayed"), id="nonce from another attempt"),
        pytest.param(id_token(nonce=None), id="no nonce"),
    ],
)
def test_untrustworthy_tokens_are_rejected(token: str) -> None:
    with pytest.raises(GoogleSignInError):
        verify(token)


def test_pkce_challenge_matches_rfc_7636_example() -> None:
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"

    assert pkce_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
