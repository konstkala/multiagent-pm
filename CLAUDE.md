# Multiagent PM

AI-assisted project management. Managers run projects with their teams; agents classify and size tickets, build employee profiles from CVs, and recommend assignees. People make every consequential decision.
Product plan: `docs/plans/2026-10-16-product-v1.md`.
Also a learning project: it should make me an expert **DevOps engineer** and **AI engineer**. Measure cost and performance on everything.

## Stack
- **Backend**: Python 3.12, FastAPI (async), Pydantic v2, `uv`
- **Agents**: jobs on a Postgres queue + a worker; state and human review in the database; one structured call per step through `core/llm`
- **DB**: Postgres 17 + pgvector. Local: Docker. Cloud: Neon free tier
- **Queue / pub-sub**: Postgres (`SKIP LOCKED`, `LISTEN/NOTIFY`). No Redis until a measured need
- **LLM**: Claude API
  - `claude-haiku-5-5`: workers (classify, summarize, extract)
  - `claude-sonnet-5-5`: orchestrator, planning, agentic tool loops
- **Embeddings**: fastembed `BAAI/bge-small-en-v1.5`, run locally on CPU
- **Observability**: Langfuse (traces, tokens, cost per run)
- **Frontend**: Next.js 16 + React 19 + TypeScript, Tailwind CSS 4, TanStack Query, Recharts. API client generated from FastAPI's OpenAPI schema; `/api` proxied to FastAPI

## Layout (planned)
```
backend/app/
  api/        FastAPI routers. Thin: validate → call service
  services/   business logic (raise DomainError; commit; write audit logs)
  schemas/    Pydantic request/response models
  agents/     graphs, nodes, prompts, tools
  db/         models, migrations
  core/       config, logging, errors, security (hashing, tokens), LLM client
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
- Fake inbox (Mailpit, part of the compose stack): http://localhost:8025
- Frontend (from `frontend/`): `npm run dev` (http://localhost:3000) · `npm run check` (lint + types + build) · `npm run gen:api` after API changes
- Worker (from `backend/`): `uv run python -m app.worker` · in Docker it's the `worker` service
- Whole stack in Docker (repo root): `docker compose up -d --build` (db → migrate job → api :8000 → web :3000). Stop local dev servers first: same ports
- Test all: `uv run pytest` (needs DB) · without DB: `uv run pytest -m "not db and not llm"`
- Real embedding model test (free, downloads the model once): `uv run pytest -m model`
- Real object storage test: `docker compose up -d storage`, then `uv run pytest -m storage`
- Test one: `uv run pytest tests/test_health.py::test_health_returns_ok`
- Tests use a throwaway `pm_test` database built from the migrations; each test is rolled back
- Check (run before saying done): `uv run ruff check --fix . && uv run ruff format . && uv run pyright && uv run pytest`
- Smoke the running stack (from `backend/`, after `docker compose up -d --build --wait`): `uv run python -m scripts.smoke` (or the `/smoke` skill). Real Haiku calls, about $0.003
- Demo data (from `backend/`, stack running): `uv run python -m scripts.seed_demo`. Sign in as `demo-manager@example.com`, password `correct horse battery`. Safe to re-run
- Pre-commit hooks, once per clone: `uv tool install pre-commit==4.6.2` then `pre-commit install`
- Run the images CI published: `TAG=sha-<commit> docker compose -f docker-compose.yml -f compose.release.yml up -d --wait`
- CI: `.github/workflows/` (ci, images, codeql, e2e). Watch a run: `gh run watch`. Actions are pinned by SHA, at least 2 weeks old

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
3. Agents run as jobs with state in the database (ADR 0016); LangGraph and PydanticAI are deferred until an agent needs branching or tool loops (ADR 0009).
4. Model routing: Haiku workers, Sonnet orchestrator.
5. Next.js + TS frontend: React ecosystem, typed client from OpenAPI, suits streaming agent output and approval UIs.
6. SQLAlchemy 2 async + Alembic + asyncpg: typed ORM, versioned migrations, async driver that works on Windows.
7. Local embeddings (fastembed, bge-small, 384 dims, cosine, HNSW): $0 per call, no extra API key. See ADR 0007.
8. Triage is a fixed workflow, not an agent (0008); structured output through the gateway (0009); Postgres job queue + worker (0010).
9. Self-hosted auth: argon2id, Google OIDC, opaque session cookies stored hashed (0011).
10. Workspace → projects → per-project roles manager/employee (0012).
11. Assignment agent recommends top 3; manager picks (0013). Story points + due dates (0014).
12. Attachments in S3-compatible storage via boto3; SeaweedFS locally, S3/R2 in production (0015).
13. Assignment scoring: lazy profile embeddings, the LLM sees letters + facts only, every pick recorded for a hit rate (0017). Job priority: interactive before background (0018).
14. Ticket history in a `ticket_events` table; KPIs are SQL computed on request, rollups only once measured slow (0019).
15. CI/CD on GitHub Actions; images on GHCR with SBOM, signed provenance and Trivy; built once, deployed by tag (0020).

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
- Look at the UI, don't guess: the Playwright MCP (`.mcp.json`) opens the running app. After a UI change, screenshot it at 1440 and 390 px wide, light and dark, and compare with the chosen mockup (https://claude.ai/artifact/3jyxBC1WQxHqey8ER8CYg8, "C · Paper"). Browser tests: `npm run e2e` in `frontend/` (stack running).
- Guard hook: `.claude/hooks/guard_commands.py` blocks force pushes, history rewrites, repo deletion or visibility changes and `terraform apply|destroy`. When blocked, give the user the exact command to run.
- Prompting cheat sheet: `docs/claude-code-cheatsheet.md`.
