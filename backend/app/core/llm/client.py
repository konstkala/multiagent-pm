import logging
import time
from collections.abc import Sequence

import anthropic
import pydantic
from anthropic import AsyncAnthropic
from anthropic.types import CacheControlEphemeralParam, Message, TextBlockParam

from app.core.config import settings
from app.core.llm.budget import RunBudget
from app.core.llm.errors import BudgetExceededError, LLMError, LLMRefusalError
from app.core.llm.pricing import MODEL_FOR_TIER, cost_usd
from app.core.llm.types import Effort, LLMResult, StructuredResult, Tier, Usage, UserContent
from app.core.logging import log_fields

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 60.0


def _usage_of(response: Message) -> Usage:
    usage = response.usage
    return Usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_input_tokens or 0,
        cache_write_tokens=usage.cache_creation_input_tokens or 0,
    )


def _system(text: str) -> list[TextBlockParam]:
    # Trusted, stable text first and marked cacheable; untrusted input goes in the user turn.
    return [
        TextBlockParam(
            type="text", text=text, cache_control=CacheControlEphemeralParam(type="ephemeral")
        )
    ]


class LLMClient:
    """The only place that talks to Claude: model routing, timeouts, cost logging, run budget."""

    def __init__(self, sdk: AsyncAnthropic, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self._sdk = sdk
        self._timeout_s = timeout_s

    async def complete(
        self,
        *,
        tier: Tier,
        effort: Effort,
        system: str,
        prompt: str,
        max_tokens: int,
        budget: RunBudget,
    ) -> LLMResult:
        """`system` is trusted, stable text and is cached. `prompt` carries untrusted input."""
        self._check_budget(budget)
        model = MODEL_FOR_TIER[tier]
        started = time.perf_counter()
        try:
            response = await self._sdk.messages.create(
                model=model,
                max_tokens=max_tokens,
                output_config={"effort": effort},
                system=_system(system),
                messages=[{"role": "user", "content": prompt}],
                timeout=self._timeout_s,
            )
        except anthropic.APIError as exc:
            raise self._api_error(exc, budget, model) from exc

        usage, cost, latency_ms = self._account(response, tier, effort, budget, model, started)
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResult(
            text=text,
            model=model,
            stop_reason=response.stop_reason or "unknown",
            usage=usage,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

    async def complete_structured[T: pydantic.BaseModel](
        self,
        *,
        tier: Tier,
        effort: Effort,
        system: str,
        content: Sequence[UserContent],
        output_type: type[T],
        max_tokens: int,
        budget: RunBudget,
    ) -> StructuredResult[T]:
        """The answer comes back as a validated `output_type`, never free text to parse."""
        self._check_budget(budget)
        model = MODEL_FOR_TIER[tier]
        started = time.perf_counter()
        try:
            response = await self._sdk.messages.parse(
                model=model,
                max_tokens=max_tokens,
                output_config={"effort": effort},
                output_format=output_type,
                system=_system(system),
                messages=[{"role": "user", "content": list(content)}],
                timeout=self._timeout_s,
            )
        except anthropic.APIError as exc:
            raise self._api_error(exc, budget, model) from exc
        except pydantic.ValidationError as exc:
            logger.warning(
                "llm.invalid_output",
                extra=log_fields(run_id=budget.run_id, model=model, errors=exc.error_count()),
            )
            raise LLMError(f"{model} returned output that doesn't fit the schema") from exc

        usage, cost, latency_ms = self._account(response, tier, effort, budget, model, started)
        output = response.parsed_output
        if output is None:  # e.g. cut off by max_tokens before the JSON was complete
            raise LLMError(f"{model} gave no structured output (stop: {response.stop_reason})")
        return StructuredResult(
            output=output, model=model, usage=usage, cost_usd=cost, latency_ms=latency_ms
        )

    def _account(
        self,
        response: Message,
        tier: Tier,
        effort: Effort,
        budget: RunBudget,
        model: str,
        started: float,
    ) -> tuple[Usage, float, float]:
        """Cost, budget, the llm.call log line, and refusals: the same for every kind of call."""
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        usage = _usage_of(response)
        cost = cost_usd(model, usage)
        budget.record(cost)  # refused calls are billed too
        stop_reason = response.stop_reason or "unknown"
        logger.info(
            "llm.call",
            extra=log_fields(
                run_id=budget.run_id,
                tier=tier.value,
                model=model,
                effort=effort,
                stop_reason=stop_reason,
                latency_ms=latency_ms,
                cost_usd=round(cost, 6),
                run_spent_usd=round(budget.spent_usd, 6),
                **usage.model_dump(),
            ),
        )
        if stop_reason == "refusal":
            self._raise_refusal(response, budget, model)
        return usage, cost, latency_ms

    @staticmethod
    def _api_error(exc: anthropic.APIError, budget: RunBudget, model: str) -> LLMError:
        logger.exception(
            "llm.error",
            extra=log_fields(
                run_id=budget.run_id,
                model=model,
                error=type(exc).__name__,
                status=getattr(exc, "status_code", None),
                request_id=getattr(exc, "request_id", None),
                detail=exc.message[:300],  # API's own description; never our prompt
            ),
        )
        return LLMError(f"{model} call failed: {type(exc).__name__}")

    @staticmethod
    def _check_budget(budget: RunBudget) -> None:
        try:
            budget.ensure_available()
        except BudgetExceededError:
            logger.warning(
                "llm.budget_exceeded",
                extra=log_fields(
                    run_id=budget.run_id,
                    spent_usd=round(budget.spent_usd, 6),
                    cap_usd=budget.cap_usd,
                ),
            )
            raise

    @staticmethod
    def _raise_refusal(response: Message, budget: RunBudget, model: str) -> None:
        category = response.stop_details.category if response.stop_details else None
        logger.warning(
            "llm.refusal",
            extra=log_fields(run_id=budget.run_id, model=model, category=category),
        )
        raise LLMRefusalError(f"{model} refused the request (category: {category})")


def create_llm_client() -> LLMClient:
    key = settings.anthropic_api_key
    if key is None:
        raise LLMError("ANTHROPIC_API_KEY is not set (add it to backend/.env)")
    return LLMClient(AsyncAnthropic(api_key=key.get_secret_value()))
