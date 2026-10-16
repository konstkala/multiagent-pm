import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Backstop only: callers must not pass secrets in the first place.
_SENSITIVE_KEYS = ("password", "secret", "token", "api_key", "authorization", "cookie")


def log_fields(**fields: object) -> dict[str, dict[str, object]]:
    """Structured fields for `extra=`: logger.info("event.name", extra=log_fields(id=1))."""
    return {"fields": fields}


def _redact(fields: dict[str, object]) -> dict[str, object]:
    return {
        key: "[REDACTED]" if any(s in key.lower() for s in _SENSITIVE_KEYS) else value
        for key, value in fields.items()
    }


class JsonFormatter(logging.Formatter):
    """One JSON object per line, so log tools can parse fields without regex."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        if request_id := request_id_var.get():
            entry["request_id"] = request_id
        fields: dict[str, object] | None = getattr(record, "fields", None)
        if fields:
            entry.update(_redact(fields))
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
