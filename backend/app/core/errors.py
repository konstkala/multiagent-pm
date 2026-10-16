class DomainError(Exception):
    """Raised by services. One exception handler turns it into an HTTP response."""

    status_code = 400
    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class InvalidRequestError(DomainError):
    status_code = 422
    code = "invalid_request"
