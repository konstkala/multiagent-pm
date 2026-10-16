# 0002. Postgres + pgvector as the only datastore

Status: accepted, 2026-10-16

## Context
The domain is relational (projects, tickets, users, assignments). We also need vectors (similar tickets), agent checkpoints and a job queue.

## Decision
Postgres 17 + pgvector for data, vectors, LangGraph checkpoints, and the queue (`SKIP LOCKED`, `LISTEN/NOTIFY`). No Redis or vector DB until a measured need. Local: Docker. Cloud: Neon free tier.

## Consequences
- One system to run, back up and secure.
- Queue throughput is lower than a dedicated broker. Fine at our scale; revisit with numbers.
