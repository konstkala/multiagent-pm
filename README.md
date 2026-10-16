# Multiagent PM

Project management run by a team of AI agents. The first workflow is **ticket triage**: a new ticket is classified, checked against similar tickets for duplicates, and routed, with a human approving the risky changes.

It is also a learning project, built the way a production system would be: containers, migrations, structured logging, CI/CD, observability, and cost tracking on every LLM call.

> **Status: early development.** The backend foundation is done. The agent workflow is next. See [Roadmap](#roadmap) for what exists and what doesn't.

## Stack

| Area | Technology | Why |
|---|---|---|
| Language / API | Python 3.12, FastAPI (async), Pydantic v2 | Agent tooling is Python-first; typed endpoints generate the frontend client |
| Agents | LangGraph + PydanticAI | Durable graph state, human-in-the-loop pauses, typed LLM output |
| LLM | Claude API: Haiku 5.5 for workers, Sonnet 5.5 for orchestration | Cheap model for routine calls; routing in one place |
| Database | PostgreSQL 17 + pgvector | One database for data, vector search, agent checkpoints and the job queue |
| ORM / migrations | SQLAlchemy 2 (async), Alembic, asyncpg | Typed models, versioned schema changes |
| Dependencies | uv with a lockfile | Reproducible installs |
| Containers | Docker, Docker Compose | Same local database for everyone |
| Quality | pytest, ruff, pyright (strict) | Tests, lint, and static types |
| Observability | Structured JSON logs with request IDs (done); Langfuse tracing (planned) | Trace a request and see tokens and cost per run |
| Frontend | Next.js + TypeScript (planned) | Streaming progress and approval screens |
| Cloud / CI / IaC | GitHub Actions, Terraform, Kubernetes (planned) | See the roadmap |

Each choice is recorded with its reasoning in [docs/adr/](docs/adr/).

## Engineering practices

- **Cost is a first-class metric.** Every LLM call goes through one gateway that logs model, tokens, cache use, dollar cost and latency, and enforces a per-run budget ($0.05).
- **Untrusted input.** Ticket text never chooses tools or skips approvals.
- **Human in the loop.** Cheap-to-undo changes (labels) apply automatically; assignee and priority changes wait for approval.
- **Logging.** One JSON object per line, a `request_id` on every line, audit events for state changes, and no secrets or user text in logs. Rules: [.claude/rules/logging.md](.claude/rules/logging.md).
- **Migrations.** Every schema change is a reviewed Alembic migration; applied migrations are never edited.
- **Health checks.** `/health` (liveness) and `/health/db` (readiness) are separate on purpose.
- **Decisions are written down** as ADRs, and plans live in [docs/plans/](docs/plans/).

## Architecture

```
Client ──► FastAPI ──► services ──► PostgreSQL + pgvector
              │                          ▲
              ▼                          │ checkpoints, queue, vectors
        job queue ──► worker ──► LangGraph workflow ──► core/llm ──► Claude API
```

Ticket triage workflow (planned): embed the ticket → find similar tickets → one Haiku call returns type, priority, labels, duplicate and suggested assignee with a confidence → apply labels → pause for human approval of assignee and priority → apply. Estimated cost: about $0.001–0.002 per ticket. Details: [docs/plans/](docs/plans/2026-10-16-ticket-triage-v1.md).

## Database

PostgreSQL 17 with the **pgvector** extension, run locally in Docker (`pgvector/pgvector:pg17`). Data is kept in a Docker volume, so it survives container restarts.

- **Today:** the schema is empty apart from the migration history. Migration `0001` enables pgvector.
- **Planned tables:** tickets (with an embedding column for similar-ticket search), LLM call records for cost tracking, and the job queue. LangGraph adds its own checkpoint tables.
- **Connection (local only):** host `localhost`, port `5432`, database `pm`, user `pm`, password `pm`. These are throwaway development credentials.

Query it with `psql` inside the container:

```sh
docker compose exec db psql -U pm -d pm
```
```sql
\dt                                   -- list tables
\dx                                   -- list extensions (vector should appear)
SELECT * FROM alembic_version;        -- which migration is applied
```

Or use any SQL client (DBeaver, pgAdmin, the VS Code PostgreSQL extension) with the connection details above.

## Quick start

Requires Docker, Python 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
docker compose up -d db                  # Postgres 17 + pgvector
cd backend
uv sync                                  # install locked dependencies
cp .env.example .env                     # PowerShell: Copy-Item .env.example .env
uv run alembic upgrade head              # apply migrations
uv run fastapi dev app/main.py           # API docs at http://localhost:8000/docs
```

Run the checks:

```sh
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

## Repository layout

```
backend/app/
  api/        FastAPI routers and middleware (request IDs, request logs)
  core/       settings, structured logging
  core/llm/   LLM gateway: model routing, prompt caching, cost + budget, refusals
  db/         SQLAlchemy base and session, Alembic migrations
backend/tests/
docs/
  adr/        architecture decision records
  plans/      feature plans
  learning/   roadmap, glossary, containers-to-Kubernetes track
.claude/      project rules for the AI coding assistant used on this repo
```

## Roadmap

| Phase | What | Status |
|---|---|---|
| 0 | Backend foundation: API, config, JSON logging, Postgres + pgvector, migrations, tests | Done |
| 1 | `core/llm`: model routing, retries, cost logging, per-run budget | Built; tracing and call history table next |
| 2 | Tickets domain, API and backend Dockerfile | Planned |
| 3 | Local embeddings and similar-ticket search | Planned |
| 4 | Triage workflow with LangGraph, background worker, approval pause | Planned |
| 5 | Approval API and an evaluation set for accuracy and cost | Planned |
| 6 | Next.js frontend | Planned |
| 7 | CI/CD, cloud deployment with Terraform, tracing and alerts | Planned |
| 8 | Kubernetes (local cluster, Helm, GitOps) | Planned |

More: [CLAUDE.md](CLAUDE.md) (project conventions) · [docs/learning/roadmap.md](docs/learning/roadmap.md) · [docs/adr/](docs/adr/)
