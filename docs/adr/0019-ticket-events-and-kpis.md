# 0019. Ticket events for history; KPIs computed on request

Status: accepted, 2026-10-17.

## Context
Milestone 6 needs throughput per week, cycle time and lead time. Tickets only stored `created_at` and `updated_at`, and audit logs live in log files, not in the database. Status history wasn't queryable.

## Decision
- A `ticket_events` table records creation, status moves and assignee changes: who, from → to, and when. It's written in the same transaction as the change, so history can't drift from the ticket.
- `project_id` is copied onto each event, because tickets never change project. Dashboards then filter one indexed table without a join.
- A separate data migration (0016) backfills events from the tickets' state at the time. Older history is therefore approximate, and the dashboard says from which date it is exact.
- KPIs are plain SQL aggregates (`percentile_cont`, `date_trunc('week')`), computed on each request and timed in the logs. We measure before precomputing.

## Consequences
- Exact cycle and lead time from now on. Reopening a ticket is kept in the history, and the table can also power an activity feed.
- Each status or assignee change writes one extra row: negligible.
- Production version, once queries get slow (rule of thumb: p95 over 300 ms, or millions of events): nightly rollups per project and day, or a read replica / OLAP store. The API contract stays the same.
- Rejected: `started_at` / `done_at` columns on tickets. Simpler, but they lose reopen history.
