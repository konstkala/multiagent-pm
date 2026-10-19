"""Create LangGraph's checkpoint tables (ADR 0021).

The tables belong to LangGraph: `PostgresSaver.setup()` creates and versions them itself, so
this migration only calls it. Never edit them by hand.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-19 10:05:00.000000

"""

from collections.abc import Sequence

from alembic import op
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection

from app.agents.checkpoint import psycopg_url

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("checkpoint_writes", "checkpoint_blobs", "checkpoints", "checkpoint_migrations")


def upgrade() -> None:
    url = psycopg_url(op.get_bind().engine.url.render_as_string(hide_password=False))
    # A separate autocommit connection: setup() runs its own statements and indexes.
    with Connection.connect(url, autocommit=True) as connection:
        PostgresSaver(connection).setup()  # pyright: ignore[reportArgumentType]


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")
