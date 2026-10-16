# 0010. Postgres job queue with a separate worker

Status: accepted, 2026-10-16

## Context
Triage must not run inside the HTTP request: it takes seconds, can fail, and should survive restarts. ADR 0002 keeps Postgres as the only datastore.

## Decision
A `jobs` table. Workers claim a row with `SELECT ... FOR UPDATE SKIP LOCKED` and update it in the same transaction, so concurrent workers never take the same job. Failed jobs retry with a delay up to a maximum; jobs stuck in `running` past a timeout are requeued. The worker is its own container using the same image as the API. v1 polls; `LISTEN/NOTIFY` is a later optimisation.

## Consequences
- Jobs are enqueued in the same transaction as the ticket, so a ticket can never be saved without its job, or the reverse.
- Throughput is far below a dedicated broker. Fine for this scale; revisit with measurements.
- At-least-once delivery: job handlers must be safe to run twice.
