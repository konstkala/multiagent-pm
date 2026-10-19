"""LangGraph's Postgres checkpointer (ADR 0021). Only the worker uses it, never the API."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings

# Tables LangGraph owns (db rules): Alembic autogenerate must leave them alone.
LANGGRAPH_TABLES = frozenset(
    {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
)


def psycopg_url(url: str) -> str:
    """The app speaks asyncpg; the checkpointer speaks psycopg. Same database, other driver."""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


@asynccontextmanager
async def checkpointer(database_url: str | None = None) -> AsyncGenerator[AsyncPostgresSaver]:
    """Tables come from migration 0019, so there is no setup() here."""
    url = psycopg_url(database_url or settings.database_url)
    async with AsyncPostgresSaver.from_conn_string(url) as saver:
        yield saver
