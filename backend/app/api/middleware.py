import logging
import re
import time
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.api.deps import SESSION_COOKIE
from app.api.errors import error_response
from app.core.config import settings
from app.core.logging import log_fields, request_id_var

logger = logging.getLogger(__name__)

# The header comes from the client: accept only a short safe id, so it can't inject into logs.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{1,64}")
_PROBE_PATHS = frozenset({"/health", "/health/db"})


async def log_requests(request: Request, call_next: RequestResponseEndpoint) -> Response:
    incoming = request.headers.get("x-request-id", "")
    request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid4().hex
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["x-request-id"] = request_id
        return response
    finally:
        # Probes fire every few seconds; at INFO they'd bury real traffic.
        level = logging.DEBUG if request.url.path in _PROBE_PATHS else logging.INFO
        logger.log(
            level,
            "http.request",
            extra=log_fields(
                method=request.method,
                path=request.url.path,  # path only: query strings can carry secrets
                status=status_code,
                duration_ms=round((time.perf_counter() - start) * 1000, 1),
            ),
        )
        request_id_var.reset(token)


_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_HEADER = "x-requested-with"


async def require_csrf_header(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Browsers only add custom headers to cross-site requests after a CORS check we control,
    so a forged form post from another site can't carry it."""
    if (
        request.method in _UNSAFE_METHODS
        and SESSION_COOKIE in request.cookies
        and CSRF_HEADER not in request.headers
    ):
        logger.warning("security.csrf_header_missing", extra=log_fields(path=request.url.path))
        return error_response(403, "csrf_header_missing", f"Send the {CSRF_HEADER} header")
    return await call_next(request)


async def limit_request_size(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Refuse oversized bodies from their declared size, before any of it is read or stored.
    The largest legitimate body is one attachment plus multipart overhead."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > settings.attachment_max_bytes + 2**20:
        return error_response(413, "file_too_large", "The request is too large")
    return await call_next(request)
