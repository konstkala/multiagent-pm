import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.errors import DomainError
from app.core.logging import log_fields

logger = logging.getLogger(__name__)


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    """The one error shape every endpoint returns."""

    error: ErrorBody


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump())


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        problems = {
            ".".join(str(p) for p in e["loc"][1:]) or "body": str(e["msg"]) for e in exc.errors()
        }
        # Log field names only: the rejected values can be passwords or user text.
        logger.warning("api.validation_failed", extra=log_fields(fields=sorted(problems)))
        message = "; ".join(f"{field}: {msg}" for field, msg in sorted(problems.items()))
        return error_response(422, "validation_error", message)
