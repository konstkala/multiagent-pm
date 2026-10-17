# Milestone 6: dashboards, AI metrics and calendar

## Context
Milestones 1–5 are done and verified (197 tests; smokes M2–M5 all pass). The product plan's M6 asks for KPI dashboards with time filters, an employee dashboard and a calendar of due dates. Brainstorm answers (2026-10-17): a **ticket events table** for history, **Recharts** for charts, calendar of **due dates only**, and an **AI metrics panel** in this milestone. No LLM calls are added: **$0 cost impact**. Today tickets only have `created_at`/`updated_at`, so cycle time and weekly throughput can't be computed: the events table fixes that.

Plan copied to `docs/plans/2026-10-17-milestone-6-dashboards.md` once approved; new ADR `docs/adr/0019-ticket-events-and-kpis.md`.

## Design

### Ticket history (`ticket_events`)
- Model `backend/app/db/models/ticket_event.py`: id, ticket_id (FK cascade), project_id (denormalised for dashboard queries; tickets never move projects), actor_id (nullable: agent or deleted user), kind (`created` | `status` | `assignee`), from_value / to_value (short strings: a status or a user id; nullable), created_at (`clock_timestamp()`). Indexes: (ticket_id, created_at), (project_id, kind, created_at).
- Migration 0015 creates it (schema). Migration 0016 backfills (data, separate per db rule): a `created` event at `created_at` for every ticket, plus a `status` event to the current status at `updated_at` when it isn't `todo`, and an `assignee` event when assigned. History before today is approximate; say so on the dashboard.
- Recording in `backend/app/services/tickets.py`, in the same transaction as the change, via a small helper `services/ticket_events.py::record(session, ticket, actor, kind, before, after)`:
  - `create_ticket` → `created` (+ `assignee` if assigned at creation)
  - `update_ticket` → `status` / `assignee` when those change (next to the existing `record_choice` call)
  - `return_to_manager` → `status` + `assignee`
  - copies go through `create_ticket` already.

### Project dashboard API (`GET /projects/{id}/dashboard?start=&end=`)
Service `backend/app/services/dashboards.py`, plain SQL aggregates computed on request (production version: rollup tables / materialised views; we measure first). Default range: last 30 days; buckets by ISO week (`date_trunc('week')`).
- **Throughput**: tickets moved to done per week; **created per week** next to it.
- **Cycle time** (first `in_progress` → `done`) and **lead time** (created → `done`): median and p90 in days, via `percentile_cont`, for tickets finished in the range.
- **Now**: open tickets by status, overdue count, age buckets of open tickets (≤ 7, 8–30, > 30 days).
- **Workload**: open points per person (same rule as assignment: unpointed = 3; reuse `scoring.UNPOINTED`), project-scoped.
- Permissions: any member sees team figures; the per-person workload rows are full for managers, own row only for employees (product plan: individual figures only for managers and the person).
- Log `dashboard.computed` with project id, range days and duration ms.

### AI metrics API (`GET /projects/{id}/agent-metrics?start=&end=`, managers)
- **Triage**: runs, accepted / dismissed / failed counts; per field (category, labels, priority, story points) how often the manager **kept the suggestion as is, edited it, or left it out**; auto-applied fields still in place now. Needs migration 0017: `triage_runs.accepted JSONB` (what the manager sent), written in `services/triage.py::accept`.
- **Assignment**: runs, decided, **top-1 and top-3 hit rate** (from `chosen_rank`).
- **Cost and speed per agent**: total $, $ per run, p50/p95 latency (from `cost_usd`, `latency_ms` on `triage_runs` and `assignment_runs`; scoring ms for assignment). The CV agent is per workspace: out of the project panel, noted for later.

### Employee dashboard (`GET /me/dashboard?start=&end=`) and calendar (`GET /calendar?start=&end=&project_id=&mine=`)
- My work across my projects: open tickets by status, due this week, overdue, open points, done per week.
- Calendar: tickets with a due date in range, from projects I'm a member of (`access.member_projects`), optional project filter and "assigned to me". Max range 62 days. Returns key, title, status, due date, assignee id, project id.

### Frontend (plain styling until the UI session)
- `npm install recharts@<exact version>` (React 19 compatible, ≥ 2 weeks old). Charts are client components.
- Project tab **Dashboard** (`/projects/[id]/dashboard`, added to `components/project-header.tsx`): range picker (7 / 30 / 90 days / custom), throughput vs created bar chart, cycle and lead time cards, open-by-status and age, workload table; **AI agents** section for managers (acceptance per field, hit rate, $ and p95 per agent).
- App shell links (`components/app-shell.tsx`): **My work** (`/me`) and **Calendar** (`/calendar`, month grid built by hand: a 7-column CSS grid, no calendar library; filter by project and "mine"; each ticket links to its page).
- Queries in `frontend/src/lib/queries.ts` (keys + hooks), types from `npm run gen:api`.

## Steps (commit after each)
- **6a** Events table + backfill + recording; project dashboard API; tests.
- **6b** Project dashboard UI (Recharts, range filter).
- **6c** AI metrics: `triage_runs.accepted`, API, panel.
- **6d** My work + calendar: API and UI. Docker rebuild, smoke `smoke_m6.py`, docs (plan result, ADR 0019, README, roadmap, glossary).

## Tests
- Events: create / status / assignee / return each write the right event with actor; copy gets `created`; no event when nothing changes.
- Backfill (migration test via the `pm_test` build): every ticket has a `created` event.
- Dashboard: seeded tickets with events at fixed times → throughput per week, median/p90 cycle and lead time, age buckets, overdue; range filter excludes outside events; employee sees only own workload row; outsider 404.
- Agent metrics: kept / edited / left-out counts from accepted runs; hit rate from chosen ranks; cost sums and p95; employee 403.
- Me / calendar: only my projects; `mine` filter; range limit 422; due dates outside range excluded.
- Logs: ids, counts and durations only.

## Verification
1. `uv run ruff check --fix . && uv run ruff format . && uv run pyright && uv run pytest`; `npm run check`.
2. `alembic upgrade head`, downgrade/upgrade round-trip, `alembic check`; backfill on the dev DB (existing smoke data) gives every ticket a `created` event.
3. `docker compose up -d --build`, then `smoke_m6.py` through the web proxy: create tickets, move them through statuses, accept a triage with an edit, pick a suggested assignee → dashboard numbers, agent metrics (one edited field, hit rate 100%), my work and calendar match; employee can't see agent metrics or others' workload.
4. Report dashboard p95 over 20 requests (target ≤ 300 ms at this data size).
