import asyncio
import logging
import threading
import time
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from fastembed import TextEmbedding

from app.core.config import settings
from app.core.logging import log_fields
from app.db.models.ticket import EMBEDDING_DIM

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    model_name: str

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class FastEmbedder:
    """Runs a small ONNX model on the CPU: no API key, no per-call cost."""

    def __init__(self, model_name: str, cache_dir: Path | None = None) -> None:
        self.model_name = model_name
        self._cache_dir = cache_dir
        self._model: TextEmbedding | None = None
        self._load_lock = threading.Lock()

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        # Inference is CPU-bound; a thread keeps the event loop free for other requests.
        return await asyncio.to_thread(self._embed_sync, list(texts))

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        started = time.perf_counter()
        vectors = [[float(x) for x in v] for v in model.embed(texts)]
        if vectors and len(vectors[0]) != EMBEDDING_DIM:
            raise ValueError(
                f"{self.model_name} gives {len(vectors[0])} dimensions, "
                f"the column holds {EMBEDDING_DIM}"
            )
        logger.info(
            "embeddings.embedded",
            extra=log_fields(
                model=self.model_name,
                count=len(texts),
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            ),
        )
        return vectors

    def _load(self) -> TextEmbedding:
        with self._load_lock:
            if self._model is None:
                started = time.perf_counter()
                cache = str(self._cache_dir) if self._cache_dir else None
                self._model = TextEmbedding(self.model_name, cache_dir=cache)
                logger.info(
                    "embeddings.model_loaded",
                    extra=log_fields(
                        model=self.model_name,
                        duration_ms=round((time.perf_counter() - started) * 1000, 1),
                    ),
                )
            return self._model


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """One shared instance, so the model is loaded once per process."""
    return FastEmbedder(settings.embedding_model, settings.embedding_cache_dir)
