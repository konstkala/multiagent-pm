import pytest

from app.core.llm import RunBudget, Tier, create_llm_client


@pytest.mark.llm
async def test_live_haiku_call_reports_usage_and_cost() -> None:
    client = create_llm_client()
    budget = RunBudget("live-smoke")

    result = await client.complete(
        tier=Tier.WORKER,
        effort="low",
        system="Reply with one word.",
        prompt="Say hello.",
        max_tokens=200,
        budget=budget,
    )

    assert result.text.strip()
    assert result.usage.output_tokens > 0
    assert 0 < result.cost_usd < budget.cap_usd
