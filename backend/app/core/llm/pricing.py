from dataclasses import dataclass

from app.core.llm.types import Tier, Usage

HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"

MODEL_FOR_TIER: dict[Tier, str] = {Tier.WORKER: HAIKU, Tier.ORCHESTRATOR: SONNET}


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input: float
    output: float
    cache_read: float
    cache_write: float  # 5-minute TTL, the default


# Haiku 5.5 bills $0.50 / $2.50 above 100K prompt tokens. Not modelled: our prompts are ~5K.
# Haiku cache prices are derived (read 0.1x, write 1.25x of input); check against the first bill.
PRICES: dict[str, Price] = {
    HAIKU: Price(input=0.10, output=0.50, cache_read=0.01, cache_write=0.125),
    SONNET: Price(input=2.00, output=10.00, cache_read=0.20, cache_write=2.50),
}


def cost_usd(model: str, usage: Usage) -> float:
    price = PRICES[model]
    total = (
        usage.input_tokens * price.input
        + usage.output_tokens * price.output
        + usage.cache_read_tokens * price.cache_read
        + usage.cache_write_tokens * price.cache_write
    )
    return total / 1_000_000
