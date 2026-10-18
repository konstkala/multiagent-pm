class LLMError(Exception):
    """The call failed. The SDK's own exceptions never leave the gateway."""


class BudgetExceededError(LLMError):
    """The run already spent its cap, so no further call is made."""


class LLMRequestRejectedError(LLMError):
    """The API refused the request itself (HTTP 400: e.g. an unreadable image). Retrying the
    same request will not help; changing it might."""


class LLMRefusalError(LLMError):
    """The model declined for safety reasons. Retrying the same request will not help."""
