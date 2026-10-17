import math
import re
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from anthropic import AsyncAnthropic
from anthropic.types import Usage as SdkUsage

from app.core.llm import LLMClient
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


@dataclass
class FakeParsed:
    """What `messages.parse` returns, reduced to the fields the gateway reads."""

    parsed_output: Any
    stop_reason: str = "end_turn"
    stop_details: Any = None
    content: list[Any] = field(default_factory=list[Any])
    usage: SdkUsage = field(
        default_factory=lambda: SdkUsage(
            input_tokens=6_000,
            output_tokens=700,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )
    )


class FakeClaude:
    """Stands in for the Anthropic SDK: answers `messages.parse` with what the test queues."""

    def __init__(self, *outcomes: FakeParsed | Exception) -> None:
        self.messages = self
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    async def parse(self, **kwargs: Any) -> FakeParsed:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def client(self) -> LLMClient:
        return LLMClient(cast(AsyncAnthropic, self))


def minimal_pdf(*lines: str) -> bytes:
    """A real one-page PDF with text, small enough to build by hand."""
    text = " T* ".join(
        "(" + line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj"
        for line in lines
    )
    stream = f"BT /F1 11 Tf 50 790 Td 15 TL {text} ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(pdf)


class Outbox:
    """Collects emails instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)
