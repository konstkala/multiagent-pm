"""Add split_runs (state of the ticket-splitter graph per ticket).

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-19 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPEN = sa.text("status IN ('queued', 'running', 'proposed', 'resuming')")


def upgrade() -> None:
    op.create_table(
        "split_runs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "proposed",
                "resuming",
                "applied",
                "dismissed",
                "failed",
                name="splitstatus",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("step", sa.String(length=20), nullable=True),
        sa.Column("rounds", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("proposal", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("accepted", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_ticket_ids",
            postgresql.ARRAY(sa.Uuid()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("llm_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_usd", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("latency_ms", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "calls",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_split_runs_ticket_id"), "split_runs", ["ticket_id"], unique=False)
    op.create_index(
        "uq_split_runs_open",
        "split_runs",
        ["ticket_id"],
        unique=True,
        postgresql_where=OPEN,
    )


def downgrade() -> None:
    op.drop_index("uq_split_runs_open", table_name="split_runs", postgresql_where=OPEN)
    op.drop_index(op.f("ix_split_runs_ticket_id"), table_name="split_runs")
    op.drop_table("split_runs")
