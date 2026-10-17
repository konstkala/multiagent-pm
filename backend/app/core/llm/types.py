from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from anthropic.types import DocumentBlockParam, ImageBlockParam, TextBlockParam
from pydantic import BaseModel, ConfigDict

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Tier(StrEnum):
    """What the call is for. Callers pick a tier, never a model id: routing lives in one place."""

    WORKER = "worker"
    ORCHESTRATOR = "orchestrator"


class Usage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class LLMResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    model: str
    stop_reason: str
    usage: Usage
    cost_usd: float
    latency_ms: float


# What a user turn may contain: text, images and documents (e.g. a PDF).
UserContent = TextBlockParam | DocumentBlockParam | ImageBlockParam


@dataclass(frozen=True)
class StructuredResult[T: BaseModel]:
    output: T
    model: str
    usage: Usage
    cost_usd: float
    latency_ms: float
