# 0005. Next.js + TypeScript frontend

Status: accepted, 2026-10-16

## Context
The UI streams agent progress and shows approval prompts. We want typed API calls.

## Decision
Next.js + TypeScript, with an API client generated from FastAPI's OpenAPI schema.

## Consequences
- Largest ecosystem; server components for data pages, client components for live updates.
- API changes require regenerating the client in the same change.
