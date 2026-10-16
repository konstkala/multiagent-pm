# 0006. SQLAlchemy 2 async + Alembic + asyncpg

Status: accepted, 2026-10-16

## Context
We need typed models, versioned migrations, and an async Postgres driver. Development happens on Windows. psycopg 3's async mode doesn't run on Windows' default (Proactor) event loop.

## Decision
SQLAlchemy 2 (async ORM) for models and queries, Alembic for migrations, asyncpg as the driver. Migrations live in `backend/app/db/migrations/`.

## Consequences
- Works the same on Windows and Linux without event-loop tweaks.
- LangGraph's Postgres checkpointer uses psycopg. Phase 4 decides: a second driver for the worker, or running the worker in Linux/Docker.
