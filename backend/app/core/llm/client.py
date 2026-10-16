import logging
import time

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import CacheControlEphemeralParam, Message, TextBlockParam

from app.core.config import settings
from app.core.llm.budget import RunBudget
from app.core.llm.errors import BudgetExceededError, LLMError, LLMRefusalError
from app.core.llm.pricing import MODEL_FOR_TIER, cost_usd
from app.core.llm.types import Effort, LLMResult, Tier, Usage
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
                system=[
                    TextBlockParam(
                        type="text",
                        text=system,
                        cache_control=CacheControlEphemeralParam(type="ephemeral"),
                    )
                ],
                messages=[{"role": "user", "content": prompt}],
                timeout=self._timeout_s,
            )
        except anthropic.APIError as exc:
            logger.exception(
                "llm.error",
                extra=log_fields(run_id=budget.run_id, model=model, error=type(exc).__name__),
            )
            raise LLMError(f"{model} call failed: {type(exc).__name__}") from exc

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

        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResult(
            text=text,
            model=model,
            stop_reason=stop_reason,
            usage=usage,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

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
