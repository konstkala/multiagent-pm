class LLMError(Exception):
    """The call failed. The SDK's own exceptions never leave the gateway."""


class BudgetExceededError(LLMError):
    """The run already spent its cap, so no further call is made."""


class LLMRefusalError(LLMError):
    """The model declined for safety reasons. Retrying the same request will not help."""
