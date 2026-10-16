# Plan: ticket triage v1

Source: [brainstorm](2026-10-16-ticket-triage-brainstorm.md). No code exists yet, so the plan starts with the foundations.

Each phase ends with: tests pass, CLAUDE.md commands updated, cost impact noted.

## Phase 0: Foundations (no LLM calls, $0)
1. Repo hygiene: `.gitignore`, `.env.example`, short `README.md`.
2. Backend scaffold with `uv`: `backend/pyproject.toml` (Python 3.12), FastAPI, Pydantic v2, pydantic-settings.
3. `core/config.py` (settings from env) and `core/logging.py` (JSON logs).
4. `app/main.py` with `GET /health` (app + DB check).
5. `docker-compose.yml`: Postgres 17 + pgvector (`pgvector/pgvector:pg17`).
6. DB layer: SQLAlchemy 2 async + Alembic, asyncpg driver (psycopg's async mode doesn't run on Windows' default event loop). First migration: `CREATE EXTENSION vector`. LangGraph's checkpointer needs psycopg: decide in Phase 4.
7. Tooling: ruff (lint + format), pyright, pytest + pytest-asyncio.
8. Tests: health endpoint, DB connectivity.
9. ADRs 0001–0005 for the existing decisions, 0006 for SQLAlchemy + Alembic + psycopg.
10. Fill the CLAUDE.md `## Commands` section.

Status: done 2026-10-16 except the DB-backed checks, which wait for Docker Desktop.

## Phase 0.5: DevOps foundations ($0)
- GitHub remote, protected `main`, PR workflow.
- GitHub Actions CI: ruff, pyright, pytest with a Postgres + pgvector service container, uv cache.
- pre-commit: ruff, gitleaks.
- Dependabot for Python, npm, Actions.

Deferred by choice: Phase 0.5 (GitHub, CI) until later; work stays on `main` for now.

## Phase 1: `core/llm` (the single gateway for LLM calls)
Status: gateway done 2026-10-16 (routing, cost, budget, refusals, logs, 11 tests with fakes). First real Haiku call passed. Still open: `llm_calls` table, Langfuse tracing.
- Model routing (`worker` → Haiku 5.5, `orchestrator` → Sonnet 5.5), explicit effort per call.
- Retries, timeouts, `stop_reason: "refusal"` handling.
- Cost: price table + per-call usage (tokens in/out, cache read/write, $, latency) → `llm_calls` table.
- Per-run budget guard ($0.05): refuses the next call once the run would exceed it.
- Langfuse tracing.
- Tests use a fake client, no real calls. Cost impact: $0 (no callers yet).

## Phase 2: Tickets domain
- `tickets` model + migration, service, CRUD API (`/tickets`), paginated list.
- Fields include type, priority, component, labels, assignee, `duplicate_of`, embedding.
- Backend Dockerfile (multi-stage, non-root, HEALTHCHECK); Trivy scan in CI.

## Phase 3: Embeddings + similar tickets
- Local embeddings (fastembed), stored in a vector column with an HNSW index.
- `find_similar(ticket, k)` service. Cost: $0 per call. Measure CPU latency.
- ADR 0007: local embeddings.

## Phase 4: Triage workflow
- Job queue on Postgres (`SKIP LOCKED`); worker process.
- LangGraph graph: embed → retrieve → classify (PydanticAI, Haiku, structured output) → apply labels/type → interrupt for assignee + priority → apply.
- Postgres checkpointer. Triage runs on ticket creation.
- Check: PydanticAI uses native structured output, not forced `tool_choice`.
- Cost impact: ~$0.001–0.002 per ticket.
- ADR 0008: triage as a workflow, not an agent.

## Phase 5: Approval API + eval
- `GET /approvals`, `POST /approvals/{id}` (approve / reject / edit) → resumes the graph.
- Eval: ~30 hand-labelled tickets, accuracy per field + $/run + p95. ~$0.05 per eval run.

## Phase 6: Frontend (Next.js)
- Ticket list, ticket detail, approval panel with `confidence` + `reason`, cost per run.

## Phase 7: Deploy
- Choose a cloud (ADR). Terraform for DB, container service, secrets, DNS.
- CD: build → push to GHCR → migrate → deploy to staging → promote to prod; rollback path.
- OpenTelemetry traces + metrics, dashboards, alerts on the p95 and error-rate SLOs.
- Load test (k6), backup + restore drill, cloud cost alerts.

## Phase 8: Kubernetes (learning track, modules 10–12)
- kind cluster locally: backend + worker Deployments, Service, Ingress, probes, ConfigMap/Secret.
- Helm chart, migration Job, HPA under k6 load, rollout + rollback.
- Argo CD (GitOps). ADR: k8s or a simpler platform for prod.

## Later
- Escalate low confidence to Sonnet 5.5.
- Batch API for backfilling existing tickets (50% cheaper).
