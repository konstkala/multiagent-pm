import math
import re
import zlib
from collections.abc import Sequence

from app.db.models.ticket import EMBEDDING_DIM
from app.services.email import EmailMessage


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


class Outbox:
    """Collects emails instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)
