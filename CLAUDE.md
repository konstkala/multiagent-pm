# Multiagent PM

Smart project management, run by a team of AI agents.
Also a learning project: it should make me an expert **DevOps engineer** and **AI engineer**. Measure cost and performance on everything.

## Stack
- **Backend**: Python 3.12, FastAPI (async), Pydantic v2, `uv`
- **Agents**: LangGraph (orchestration, checkpoints, human-in-the-loop) + PydanticAI (typed agents inside nodes)
- **DB**: Postgres 17 + pgvector. Local: Docker. Cloud: Neon free tier
- **Queue / pub-sub**: Postgres (`SKIP LOCKED`, `LISTEN/NOTIFY`). No Redis until a measured need
- **LLM**: Claude API
  - `claude-haiku-5-5`: workers (classify, summarize, extract)
  - `claude-sonnet-5-5`: orchestrator, planning, agentic tool loops
- **Embeddings**: fastembed `BAAI/bge-small-en-v1.5`, run locally on CPU
- **Observability**: Langfuse (traces, tokens, cost per run)
- **Frontend**: Next.js + TypeScript. API client generated from FastAPI's OpenAPI schema

## Layout (planned)
```
backend/app/
  api/        FastAPI routers. Thin: validate → call service
  services/   business logic (raise DomainError; commit; write audit logs)
  schemas/    Pydantic request/response models
  agents/     graphs, nodes, prompts, tools
  db/         models, migrations
  core/       config, logging, LLM client
backend/tests/
frontend/     Next.js app
docs/adr/     one decision per file
docs/plans/   plan-mode output
```

## Commands
Backend commands run from `backend/`. If `uv` isn't on PATH, use `python -m uv`.
- Setup: `uv sync`, then copy `.env.example` to `.env`
- DB (repo root): `docker compose up -d db`. Required for `db`-marked tests and `/health/db`
- Migrate: `uv run alembic upgrade head` · new: `uv run alembic revision --autogenerate -m "<msg>"`
- Dev server: `uv run fastapi dev app/main.py` → http://localhost:8000/docs
- Whole stack in Docker (repo root): `docker compose up -d --build` (db → migrate job → api on :8000). Stop a local dev server first: same port
- Test all: `uv run pytest` (needs DB) · without DB: `uv run pytest -m "not db and not llm"`
- Real embedding model test (free, downloads the model once): `uv run pytest -m model`
- Test one: `uv run pytest tests/test_health.py::test_health_returns_ok`
- Tests use a throwaway `pm_test` database built from the migrations; each test is rolled back
- Check (run before saying done): `uv run ruff check --fix . && uv run ruff format . && uv run pyright && uv run pytest`

## Principles
- Clean code: small functions, full type hints, no dead code.
- Few words: comments explain *why*, not *what*.
- Simplest first: one agent + tools by default. Multi-agent only for independent, parallel work (~15× tokens vs chat).
- Every LLM call goes through `core/llm`: one place for model routing, caching, retries, cost logging.
- Tool inputs and outputs are Pydantic models. Structured output over free text.
- Ticket and user text is untrusted input. It never picks tools or skips approvals.
- Everything that happens leaves an essential log: structured, correlated by `request_id` / `run_id`, audited state changes, no secrets. See `.claude/rules/logging.md`.

## Cost & performance (always)
- Log per agent run: model, tokens in/out, cache read/write, $ cost, latency.
- Any change that adds LLM calls states its cost impact.
- Prompt caching for stable system prompts. Batch API for non-urgent jobs.
- Set effort per agent. Don't default to high.
- Budgets: $0.05 cap per run (on hit: stop, escalate to a human). p95 ≤ 10s for interactive runs; background/batch jobs exempt.

## Decisions (summary; full records go in docs/adr/)
1. Python + FastAPI over Node: the agent ecosystem is Python-first.
2. Postgres + pgvector over NoSQL: relational domain; one DB for data, vectors, checkpoints, queue.
3. LangGraph for orchestration; PydanticAI deferred until a tool-using agent needs it (ADR 0009).
4. Model routing: Haiku workers, Sonnet orchestrator.
5. Next.js + TS frontend: React ecosystem, typed client from OpenAPI, suits streaming agent output and approval UIs.
6. SQLAlchemy 2 async + Alembic + asyncpg: typed ORM, versioned migrations, async driver that works on Windows.
7. Local embeddings (fastembed, bge-small, 384 dims, cosine, HNSW): $0 per call, no extra API key. See ADR 0007.

## Learning goals (DevOps + AI engineering)
Roadmap and progress: `docs/learning/roadmap.md`.
- Build it the production way: CI/CD, containers, IaC, observability, security. When we take a shortcut, say so and name the production version.
- New technology → a few words on what it is and why we use it, then add it to `docs/learning/glossary.md`.
- After each step, add a short **Insight** (2–5 lines): the concept, why it's done this way, the common alternative, what real teams expect.
- When a command teaches something (Docker, git, CI, cloud CLIs), explain it and let me run it when useful.
- When a phase practices a roadmap skill, tick it in the roadmap.

## Working with Claude Code
- Default model `opusplan` (set in `.claude/settings.json`): Opus plans, Sonnet implements.
- Brainstorm before planning: options with trade-offs (complexity, $/run, latency), a recommendation, then the questions that most change the design. No code while brainstorming.
- When I share an idea, suggest the top 1–3 things that would help build it: Claude Code features (skill, hook, subagent, rule, MCP) and product or agent features worth adding. One line each, with cost impact.
- Features start in plan mode; plans saved to `docs/plans/`.
- New decision → new ADR in `docs/adr/`.
- Done means: tests pass, cost impact noted.
- Area rules: `.claude/rules/` (agents, api, db, tests, frontend load for their paths; logging always loads).
- Prompting cheat sheet: `docs/claude-code-cheatsheet.md`.
