# Multiagent PM

Project management run by a team of AI agents. The first workflow is **ticket triage**: a new ticket is classified, checked against similar tickets for duplicates, and routed, with a human approving the risky changes.

It is also a learning project, built the way a production system would be: containers, migrations, structured logging, CI/CD, observability, and cost tracking on every LLM call.

> **Status: early development.** Milestones 1–6 are done: accounts (email or Google), workspaces, projects and roles, a Jira-style ticket experience, invitations, three AI agents (CV → skills profile, ticket triage, assignee suggestions; a manager makes every final call), and dashboards: team KPIs, how well the agents do, your own work, and a calendar. Deployment comes next. See the [product plan](docs/plans/2026-10-16-product-v1.md) for what's next.

## Stack

| Area | Technology | Why |
|---|---|---|
| Language / API | Python 3.12, FastAPI (async), Pydantic v2 | Agent tooling is Python-first; typed endpoints generate the frontend client |
| Agents | LangGraph + PydanticAI | Durable graph state, human-in-the-loop pauses, typed LLM output |
| LLM | Claude API: Haiku 5.5 for workers, Sonnet 5.5 for orchestration | Cheap model for routine calls; routing in one place |
| Database | PostgreSQL 17 + pgvector | One database for data, vector search, agent checkpoints and the job queue |
| ORM / migrations | SQLAlchemy 2 (async), Alembic, asyncpg | Typed models, versioned schema changes |
| Embeddings | fastembed (bge-small, ONNX, CPU) + pgvector HNSW | Free, local similar-ticket search; no extra API key |
| Dependencies | uv with a lockfile | Reproducible installs |
| Containers | Docker, Docker Compose | Same local database for everyone |
| Files | S3 API via boto3; SeaweedFS locally, S3/R2 in production | Attachments outside the database; storage product swappable by config |
| Quality | pytest, ruff, pyright (strict) | Tests, lint, and static types |
| Auth | Self-hosted: argon2id passwords, opaque session cookies stored hashed, email verification and reset via SMTP (Mailpit locally); Google sign-in next | Security engineering without a vendor |
| Observability | Structured JSON logs with request IDs (done); Langfuse tracing (planned) | Trace a request and see tokens and cost per run |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, TanStack Query; typed client generated from the OpenAPI schema | Typed end to end; `/api` proxied so the session cookie stays first-party |
| Cloud / CI / IaC | GitHub Actions, Terraform, Kubernetes (planned) | See the roadmap |

Each choice is recorded with its reasoning in [docs/adr/](docs/adr/).

## Engineering practices

- **Cost is a first-class metric.** Every LLM call goes through one gateway that logs model, tokens, cache use, dollar cost and latency, and enforces a per-run budget ($0.05).
- **Untrusted input.** Ticket text never chooses tools or skips approvals.
- **Human in the loop.** Cheap-to-undo changes (labels) apply automatically; assignee and priority changes wait for approval.
- **Multi-tenancy.** Workspace → projects → per-project roles. Every query on project data checks membership; outsiders get 404 so they can't even learn a project exists. Similar-ticket search never crosses projects.
- **Authentication.** No account enumeration (same responses for known and unknown emails, equal timing), single-use hashed email tokens, sessions revoked on password reset, CSRF header check, rate limits stored in Postgres so they hold across replicas.
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

Background work runs in a separate `worker` container that pulls jobs from Postgres (`SKIP LOCKED`). The first agent, CV → profile, runs there: one structured Haiku call reading the PDF directly, about $0.0007 per CV, with the CV deleted right after.

The triage agent runs there too. A new ticket queues a run; the worker gathers similar tickets (pgvector), the project's labels and image attachments, and one Haiku call returns category, labels, priority, story points and a possible duplicate, each with a confidence. Category and labels apply by themselves only when the agent is confident and the field is empty; everything else waits for a manager to accept (with edits) or dismiss. If a ticket is too vague to size, the agent asks one question first. Measured: **$0.0001 and ~2 s per ticket**. Ticket text is passed as data in tagged blocks the text can't close, and code validates every field the model returns. Details: [plan](docs/plans/2026-10-17-milestone-4-triage.md), [ADR 0016](docs/adr/0016-triage-without-langgraph.md).

The assignment agent suggests who should take a ticket. Code ranks the project's members, for free and in about 80 ms: skill fit (ticket vs profile embedding, plus labels that match a named skill), similar tickets they finished, and availability (open points vs the team average, minus overdue work). The top 3 appear at once, each with its facts. One Haiku call then writes a reason for each one, seeing **letters and facts only, never names**. The manager assigns as usual, and every pick is recorded with its rank, which gives the agent's hit rate. Measured: **$0.00012 per click, reasons in ~4 s**. A job priority stops the click waiting behind background triage. Details: [plan](docs/plans/2026-10-17-milestone-5-assignment.md), [ADR 0017](docs/adr/0017-assignment-scoring.md), [ADR 0018](docs/adr/0018-job-priority.md).

Dashboards are computed on request with plain SQL over a `ticket_events` history table (status and assignee changes, written in the same transaction as the change). The project dashboard has a p95 of **22 ms** through the web proxy. Managers also see how the agents perform, from data the app records anyway: per triage field, how often managers kept, edited or dropped the suggestion; the assignment hit rate; and $ and latency per agent. No LLM calls: **$0**. Details: [plan](docs/plans/2026-10-17-milestone-6-dashboards.md), [ADR 0019](docs/adr/0019-ticket-events-and-kpis.md).

## API

| Method | Path | Purpose |
|---|---|---|
| POST, GET | `/workspaces` | Create a workspace (you become owner); list yours |
| POST, GET | `/workspaces/{id}/projects` | Owners create projects (creator becomes manager); list your projects |
| GET | `/projects/{id}` | Project with your role |
| GET, POST | `/projects/{id}/members` | List members; managers add a verified user by email as manager or employee |
| PATCH, DELETE | `/projects/{id}/members/{user_id}` | Change role or remove; a project always keeps one manager |
| POST | `/projects/{id}/tickets` | Create a ticket (numbered per project: PM-1, PM-2, ...) |
| GET | `/projects/{id}/tickets` | List with filters: `status` (repeatable), `assignee_id`, `unassigned`, `category`, `label`, `parent_id`, `q`; paginated |
| GET | `/tickets/{id}` | Read one |
| PATCH | `/tickets/{id}` | Change fields (managers) or move status (assignee); null clears optional ones |
| POST | `/tickets/{id}/copy`, `/tickets/{id}/return` | Copy as a template (managers); return to the manager with a reason (assignee) |
| GET, POST | `/tickets/{id}/comments` · PATCH, DELETE `/comments/{id}` | Comments; authors edit their own, managers can delete any |
| GET, POST | `/tickets/{id}/links` · DELETE `/links/{id}` | "blocks" and "relates to", shown on both tickets |
| GET, POST | `/tickets/{id}/attachments` · GET `/attachments/{id}/download` · DELETE | Files up to 10 MB, type checked from content, served sandboxed |
| GET | `/tickets/{id}/similar` | Most similar tickets in the same project (`limit`, `min_similarity`) |
| POST | `/auth/sign-up`, `/auth/verify-email`, `/auth/resend-verification` | Create an account and confirm the email |
| POST | `/auth/sign-in`, `/auth/sign-out` · GET `/auth/me` | Session cookie sign-in |
| POST | `/auth/forgot-password`, `/auth/reset-password` | Reset by email link |
| POST, GET | `/projects/{id}/invitations` · DELETE `/invitations/{id}` | Invite by email, list pending, revoke |
| POST | `/invitations/preview`, `/invitations/accept` | Token in the body; accepting needs the invited, verified email |
| GET | `/workspaces/{id}/people` · GET, PUT `.../people/{user}/profile` | People and profiles (managers, or yourself) |
| POST | `/workspaces/{id}/people/{user}/cv` | Upload a PDF CV: 202, the CV agent drafts a profile in the background |
| GET, POST | `/cv-imports/{id}` · `/approve` · `/reject` | Review the draft (with cost and latency), approve with edits or reject |
| GET, POST | `/tickets/{id}/triage` | Latest triage run (members); re-run: 202 (managers) |
| POST | `/triage-runs/{id}/answer` · `/accept` · `/dismiss` | Answer the agent's question, accept the suggestion with edits, or dismiss (managers) |
| GET, POST | `/tickets/{id}/assignment-suggestions` | Latest suggestions; ask for new ones: 202 with the ranked top 3, reasons follow (managers) |
| GET | `/projects/{id}/dashboard` | Created and done per week, cycle and lead time (median, p90), open by status and age, overdue, workload (`start`, `end`) |
| GET | `/projects/{id}/agent-metrics` | Per agent: what managers kept, edited or left out, assignment hit rate, $ and latency p50/p95 (managers) |
| GET | `/me/dashboard` · `/calendar` | Your open work, due soon, overdue, done per week; tickets due in a range (`mine` to filter) |
| GET | `/health`, `/health/db` | Liveness, readiness |

Everything except `/health` and `/auth/*` requires sign-in, and people outside a project get 404 for it. Requests that change state while signed in must send an `X-Requested-With` header (CSRF protection). Errors always look like `{"error": {"code": "...", "message": "..."}}`. Interactive docs at `/docs`.

## Database

PostgreSQL 17 with the **pgvector** extension, run locally in Docker (`pgvector/pgvector:pg17`). Data is kept in a Docker volume, so it survives container restarts.

- **Migrations:** `0001` enables pgvector, `0002` creates `tickets`, `0003` adds embeddings.
- **`tickets`:** UUID keys, text columns with CHECK constraints for status/type/priority, labels array, self-referencing `duplicate_of`, timestamps. Triage fields are empty until triage runs.
- **Embeddings:** migration `0003` adds a `vector(384)` column, the model name, and an HNSW cosine index.
- **Planned:** LLM call records for cost tracking and the job queue. LangGraph adds its own checkpoint tables.
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

Or run everything in containers (database, migration job, API, web app, fake inbox):

```sh
docker compose up -d --build             # app http://localhost:3000 · API docs http://localhost:8000/docs · inbox http://localhost:8025
docker compose down                      # stop; data is kept in a volume
```

Run the checks:

```sh
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

## Repository layout

```
backend/app/
  api/        FastAPI routers, error handlers, middleware (request IDs, request logs)
  services/   business logic and audit logging
  schemas/    request and response models
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
| M1 | Auth (email + Google), workspaces, projects, roles, Next.js app shell | Done |
| 2 | Tickets domain, API and backend Dockerfile | Done |
| M2 | Ticket workflow, sub-tasks, links, comments, attachments; list, board and detail screens | Done |
| M3 | Invitations, employee profiles, job queue + worker, **CV agent** (Haiku reads a PDF CV, a manager reviews) | Done |
| 3 | Local embeddings and similar-ticket search | Done |
| M4 | **Triage agent**: category, labels, priority, points, duplicates; one clarifying question; manager approval | Done |
| M5 | **Assignment agent**: top 3 by skills, past work and workload; reasons from facts only; picks recorded | Done |
| M6 | **Dashboards**: ticket history, team KPIs, AI agent metrics (acceptance per field, hit rate, $, p95), my work, calendar | Done |
| 5 | Approval API; evaluation set from recorded manager decisions | Approval API done; eval set planned |
| 6 | Next.js frontend | Built across M1–M6; design pass pending |
| 7 | CI/CD, cloud deployment with Terraform, tracing and alerts | Next |
| 8 | Kubernetes (local cluster, Helm, GitOps) | Planned |

More: [CLAUDE.md](CLAUDE.md) (project conventions) · [docs/learning/roadmap.md](docs/learning/roadmap.md) · [docs/adr/](docs/adr/)
