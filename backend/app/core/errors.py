class DomainError(Exception):
    """Raised by services. One exception handler turns it into an HTTP response."""

    status_code = 400
    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnauthorizedError(DomainError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(DomainError):
    status_code = 403
    code = "forbidden"


class EmailNotVerifiedError(ForbiddenError):
    code = "email_not_verified"


class RateLimitedError(DomainError):
    status_code = 429
    code = "rate_limited"


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class InvalidRequestError(DomainError):
    status_code = 422
    code = "invalid_request"
