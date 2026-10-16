import json
import logging

import pytest
from httpx import AsyncClient

from app.core.logging import JsonFormatter, request_id_var


def format_record(**fields: object) -> dict[str, object]:
    record = logging.makeLogRecord({"msg": "test.event", "fields": fields})
    return json.loads(JsonFormatter().format(record))


def test_formatter_writes_event_and_fields() -> None:
    entry = format_record(ticket_id=7)

    assert entry["event"] == "test.event"
    assert entry["ticket_id"] == 7


def test_formatter_redacts_sensitive_keys() -> None:
    entry = format_record(api_key="sk-123", auth_token="abc", user_id=1)

    assert entry["api_key"] == "[REDACTED]"
    assert entry["auth_token"] == "[REDACTED]"
    assert entry["user_id"] == 1


def test_formatter_includes_request_id_from_context() -> None:
    token = request_id_var.set("req-1")
    try:
        entry = format_record()
    finally:
        request_id_var.reset(token)

    assert entry["request_id"] == "req-1"


async def test_middleware_returns_generated_request_id(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert len(response.headers["x-request-id"]) == 32


async def test_middleware_keeps_valid_incoming_request_id(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"x-request-id": "abc-123"})

    assert response.headers["x-request-id"] == "abc-123"


async def test_middleware_replaces_unsafe_incoming_request_id(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"x-request-id": "<script>"})

    assert response.headers["x-request-id"] != "<script>"


async def test_middleware_logs_request_without_query_string(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="app.api.middleware")

    await client.get("/health?token=secret")

    record = next(r for r in caplog.records if r.getMessage() == "http.request")
    fields = record.__dict__["fields"]
    assert fields["path"] == "/health"
    assert fields["status"] == 200
    assert "secret" not in json.dumps(fields)
