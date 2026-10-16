import json
import logging
from typing import Any, cast

import anthropic
import httpx2
import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock
from anthropic.types import Usage as SdkUsage

from app.core.llm import (
    BudgetExceededError,
    LLMClient,
    LLMError,
    LLMRefusalError,
    RunBudget,
    Tier,
    Usage,
)
from app.core.llm.pricing import HAIKU, SONNET, cost_usd


def make_message(
    text: str = "ok",
    *,
    model: str = HAIKU,
    stop_reason: str = "end_turn",
    input_tokens: int = 1000,
    output_tokens: int = 200,
    cache_read: int = 0,
    cache_write: int = 0,
) -> Message:
    return Message.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [TextBlock(type="text", text=text, citations=None)],
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": SdkUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_input_tokens=cache_read,
                cache_creation_input_tokens=cache_write,
            ),
        }
    )


class FakeMessages:
    def __init__(self, outcome: Message | Exception) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Message:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeSdk:
    def __init__(self, outcome: Message | Exception) -> None:
        self.messages = FakeMessages(outcome)


def make_client(outcome: Message | Exception) -> tuple[LLMClient, FakeMessages]:
    sdk = FakeSdk(outcome)
    return LLMClient(cast(AsyncAnthropic, sdk)), sdk.messages


async def complete(client: LLMClient, budget: RunBudget, tier: Tier = Tier.WORKER) -> str:
    result = await client.complete(
        tier=tier,
        effort="low",
        system="You triage tickets.",
        prompt="Printer is on fire",
        max_tokens=500,
        budget=budget,
    )
    return result.text


def test_cost_usd_sums_all_token_kinds() -> None:
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000, cache_read_tokens=1_000_000)

    assert cost_usd(HAIKU, usage) == pytest.approx(0.10 + 0.50 + 0.01)
    assert cost_usd(SONNET, usage) == pytest.approx(2.00 + 10.00 + 0.20)


def test_budget_refuses_once_cap_is_reached() -> None:
    budget = RunBudget("run-1", cap_usd=0.01)
    budget.record(0.01)

    with pytest.raises(BudgetExceededError):
        budget.ensure_available()


async def test_complete_routes_worker_tier_to_haiku_with_cached_system() -> None:
    client, messages = make_client(make_message("hello"))

    text = await complete(client, RunBudget("run-1"))

    call = messages.calls[0]
    assert text == "hello"
    assert call["model"] == HAIKU
    assert call["output_config"] == {"effort": "low"}
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert call["messages"] == [{"role": "user", "content": "Printer is on fire"}]
    assert "temperature" not in call


async def test_complete_routes_orchestrator_tier_to_sonnet() -> None:
    client, messages = make_client(make_message(model=SONNET))

    await complete(client, RunBudget("run-1"), Tier.ORCHESTRATOR)

    assert messages.calls[0]["model"] == SONNET


async def test_complete_records_cost_in_budget_and_result() -> None:
    client, _ = make_client(make_message(input_tokens=2000, output_tokens=500, cache_read=3000))
    budget = RunBudget("run-1")

    result = await client.complete(
        tier=Tier.WORKER, effort="low", system="s", prompt="p", max_tokens=500, budget=budget
    )

    expected = (2000 * 0.10 + 500 * 0.50 + 3000 * 0.01) / 1_000_000
    assert result.cost_usd == pytest.approx(expected)
    assert budget.spent_usd == pytest.approx(expected)
    assert result.usage.cache_read_tokens == 3000


async def test_complete_logs_call_without_prompt_text(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.core.llm.client")
    client, _ = make_client(make_message())

    await complete(client, RunBudget("run-7"))

    record = next(r for r in caplog.records if r.getMessage() == "llm.call")
    fields = record.__dict__["fields"]
    assert fields["run_id"] == "run-7"
    assert fields["model"] == HAIKU
    assert fields["input_tokens"] == 1000
    assert "Printer is on fire" not in json.dumps(fields)


async def test_complete_refuses_before_calling_when_budget_spent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, messages = make_client(make_message())
    budget = RunBudget("run-1", cap_usd=0.01)
    budget.record(0.02)

    with pytest.raises(BudgetExceededError):
        await complete(client, budget)

    assert messages.calls == []
    assert any(r.getMessage() == "llm.budget_exceeded" for r in caplog.records)


async def test_complete_raises_on_refusal_and_still_counts_cost() -> None:
    client, _ = make_client(make_message(stop_reason="refusal"))
    budget = RunBudget("run-1")

    with pytest.raises(LLMRefusalError):
        await complete(client, budget)

    assert budget.spent_usd > 0


async def test_complete_wraps_sdk_errors() -> None:
    error = anthropic.APIConnectionError(
        request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    client, _ = make_client(error)

    with pytest.raises(LLMError):
        await complete(client, RunBudget("run-1"))
