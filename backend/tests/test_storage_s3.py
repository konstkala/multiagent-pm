import uuid

import pytest

from app.services.storage import get_storage


@pytest.mark.storage
async def test_real_s3_storage_round_trip() -> None:
    """Against the compose `storage` service (SeaweedFS): docker compose up -d storage."""
    storage = get_storage()
    key = f"tests/{uuid.uuid4().hex}"

    await storage.put(key, b"hello", "text/plain; charset=utf-8")
    data = await storage.get(key)
    await storage.delete(key)

    assert data == b"hello"
