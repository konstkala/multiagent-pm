---
paths:
  - "backend/tests/**"
---
# Tests

- Unit tests make no real LLM calls. Use PydanticAI `TestModel` / `FunctionModel` or a fake `core/llm`.
- Tests that call the real Claude API are marked `@pytest.mark.llm` and excluded by default: they cost money.
- Integration tests use real Postgres (Docker), not SQLite. pgvector and `SKIP LOCKED` need it.
- Tests are independent: each runs in a rolled-back transaction or a fresh schema.
- Assert on structured output and state, never on LLM wording.
- Cover the guardrails: untrusted input can't pick tools or skip approval; the budget cap stops a run.
- Bug fix → write the failing regression test first.
- Name tests `test_<unit>_<behaviour>`.
