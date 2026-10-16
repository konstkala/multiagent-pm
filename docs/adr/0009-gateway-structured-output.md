# 0009. Structured output through the gateway; PydanticAI deferred

Status: accepted, 2026-10-16. Amends ADR 0003.

## Context
ADR 0003 chose LangGraph + PydanticAI. PydanticAI makes its own Claude calls, which would bypass `core/llm` (cost logging, run budget, refusal handling). The Anthropic SDK can return a validated Pydantic object itself (`messages.parse`).

## Decision
Triage calls `LLMClient.complete_structured()`, which wraps `messages.parse`. LangGraph stays. PydanticAI is added when an agent needs tool loops, and then through an adapter that keeps calls going through the gateway.

## Consequences
- One place for cost, budget and refusals; one library fewer for now.
- If the SDK helper changes, only the gateway changes.
