import math
import re
import zlib
from collections.abc import Sequence

from app.db.models.ticket import EMBEDDING_DIM
from app.services.email import EmailMessage
from app.services.google import GoogleIdentity, GoogleSignInError
from app.services.storage import StorageError


class FakeEmbedder:
    """Hashes words into a fixed-size vector: texts sharing words get a high cosine similarity."""

    model_name = "fake-bag-of-words"

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            vector[zlib.crc32(word.encode()) % EMBEDDING_DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]


class BrokenEmbedder:
    model_name = "broken"

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("model unavailable")


class FakeGoogle:
    """Stands in for Google: hands back whatever identity the test sets."""

    def __init__(self) -> None:
        self.identity = GoogleIdentity(
            subject="google-sub-1", email="ada@example.com", email_verified=True, name="Ada L"
        )
        self.last_state: str | None = None
        self.last_nonce: str | None = None
        self.fail = False

    def authorization_url(self, *, state: str, nonce: str, code_challenge: str) -> str:
        self.last_state, self.last_nonce = state, nonce
        return f"https://accounts.example/auth?state={state}&challenge={code_challenge}"

    async def identity_from_code(
        self, *, code: str, code_verifier: str, nonce: str
    ) -> GoogleIdentity:
        if self.fail or nonce != self.last_nonce:
            raise GoogleSignInError("rejected")
        return self.identity


class MemoryStorage:
    """Object storage in a dict. `fail` simulates the storage service being down."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail = False

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self._check()
        self.objects[key] = (data, content_type)

    async def get(self, key: str) -> bytes:
        self._check()
        return self.objects[key][0]

    async def delete(self, key: str) -> None:
        self._check()
        self.objects.pop(key, None)

    def _check(self) -> None:
        if self.fail:
            raise StorageError("down")


class Outbox:
    """Collects emails instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)
