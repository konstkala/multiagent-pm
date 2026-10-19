import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.agents.checkpoint import LANGGRAPH_TABLES
from app.core.config import settings
from app.db import models  # noqa: F401  (registers tables for autogenerate)
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    # Default would disable every logger that already exists in this process, ours included.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def database_url() -> str:
    # Tests pass their own URL through the config; otherwise use app settings.
    return config.get_main_option("sqlalchemy.url") or settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    # LangGraph's checkpoint tables are not in our models; autogenerate must not drop them.
    return not (type_ == "table" and name in LANGGRAPH_TABLES)


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection, target_metadata=target_metadata, include_name=include_name
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # NullPool: a migration run is one short-lived connection.
    engine = create_async_engine(database_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
