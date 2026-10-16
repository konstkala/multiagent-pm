import math

import pytest

from app.core.config import settings
from app.db.models.ticket import EMBEDDING_DIM
from app.services.embeddings import FastEmbedder


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.hypot(*a) * math.hypot(*b))


@pytest.mark.model
async def test_real_model_ranks_a_reworded_duplicate_above_unrelated_text() -> None:
    embedder = FastEmbedder(settings.embedding_model, settings.embedding_cache_dir)

    original, reworded, unrelated = await embedder.embed(
        [
            "Login page returns 500 after password reset",
            "Users get a server error when resetting their password",
            "Printer on the third floor is out of toner",
        ]
    )

    assert len(original) == EMBEDDING_DIM
    assert cosine(original, reworded) > 0.65 > cosine(original, unrelated)
