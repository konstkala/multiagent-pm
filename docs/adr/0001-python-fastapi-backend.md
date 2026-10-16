# 0001. Python + FastAPI backend

Status: accepted, 2026-10-16

## Context
The product is mostly agents. Agent tooling (LangGraph, PydanticAI, the Anthropic SDK, evals) ships in Python first.

## Decision
Python 3.12 + FastAPI (async) + Pydantic v2, managed with `uv`.

## Consequences
- Agent libraries and examples are usable as-is.
- FastAPI's OpenAPI schema generates the typed frontend client.
- Two languages in the repo (Python backend, TypeScript frontend).
