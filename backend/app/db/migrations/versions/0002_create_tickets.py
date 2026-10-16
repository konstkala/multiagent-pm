"""Create the tickets table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _text_enum(name: str, *values: str) -> sa.Enum:
    # Text column + CHECK constraint: adding a value later is a plain migration.
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=20)


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "status",
            _text_enum("ticketstatus", "open", "in_progress", "resolved", "closed"),
            server_default="open",
            nullable=False,
        ),
        sa.Column(
            "labels",
            sa.ARRAY(sa.String(length=50)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("type", _text_enum("tickettype", "bug", "feature", "task", "question")),
        sa.Column("priority", _text_enum("ticketpriority", "low", "medium", "high", "urgent")),
        sa.Column("component", sa.String(length=100)),
        sa.Column("assignee", sa.String(length=100)),
        sa.Column("duplicate_of", sa.Uuid()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["duplicate_of"], ["tickets.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_tickets_created_at", table_name="tickets")
    op.drop_table("tickets")
