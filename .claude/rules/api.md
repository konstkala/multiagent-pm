---
paths:
  - "backend/app/api/**"
---
# API

- Routers are thin: validate, call one service function, return. No business logic, queries, or LLM calls.
- Every endpoint declares Pydantic request and response models. They generate the frontend client, so they are a public contract.
- Async all the way. No blocking I/O in handlers.
- Agent runs never block a request: enqueue the job, return `202` with a job id, stream progress over SSE. Keeps interactive p95 ≤ 10s.
- Services raise domain exceptions; one exception handler maps them to HTTP. One error body shape everywhere.
- Auth and current user come from a FastAPI dependency, never inline checks.
- List endpoints are paginated.
- API shape changed → regenerate the frontend client in the same change.
