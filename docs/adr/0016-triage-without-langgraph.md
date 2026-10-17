# 0016. Triage runs on the job queue, not LangGraph

Status: accepted, 2026-10-17. Amends ADR 0003 and ADR 0008.

## Context
ADR 0003/0008 planned triage as a LangGraph graph with a Postgres checkpointer and an interrupt for human approval. Since then, milestone 3 built a job queue, a worker and a review pattern (the CV agent) that already give us durable state, retries and a pause for a person. Triage has two steps at most: propose, and possibly ask one question first.

## Decision
Triage is a job. Its state lives in a `triage_runs` row (queued, needs_answer, proposed, applied, dismissed, failed). A manager's answer re-queues the run. LangGraph is deferred until an agent needs branching or tool loops, where a graph framework earns its cost.

## Consequences
- No new runtime dependencies (psycopg, checkpointer tables); the same tests, logs and cost tracking as the CV agent.
- The "pause for a person" is a database state any screen or API can read, not framework state.
- When a multi-step agent arrives (e.g. assignment with tool use), revisit LangGraph with a real need to measure against.
