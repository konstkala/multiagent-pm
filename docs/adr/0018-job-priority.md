# 0018. Job priority: a person waiting beats background work

Status: accepted, 2026-10-17. Amends ADR 0010.

## Context
The queue claimed jobs strictly oldest first. In the milestone 5 smoke run, a manager clicked "Suggest assignee" while six triage jobs (about 2 s each) were queued from tickets created a moment before. The reasons took **14.3 s** to appear although the Haiku call took 2.0 s: head-of-line blocking, over the 10 s p95 target for interactive runs.

## Decision
Jobs get a `priority`, where lower runs first (like Unix `nice`): `INTERACTIVE = 0` when someone is watching the screen for the result, `BACKGROUND = 10` by default. `claim()` orders by `(priority, run_after)`, and the runnable index covers `(status, priority, run_after)`. Only assignment reasons are interactive for now.

## Consequences
- Measured after the change: reasons in 4.2 s with the same backlog. The job now waits only for the job already running.
- Background jobs can starve if interactive ones never stop coming. That's no risk at our volume; the production answers are a second worker (or a worker per priority) and an age-based boost.
- Alternatives considered: separate queues per kind (more moving parts), more worker replicas (helps, but FIFO still blocks under load).
