"""Add triage runs (state of the triage agent per ticket).

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-17 04:36:01.035258

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "triage_runs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "needs_answer",
                "proposed",
                "applied",
                "dismissed",
                "failed",
                name="triagestatus",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            server_default="queued",
            nullable=False,
        ),
        sa.Column(
            "trigger",
            sa.Enum(
                "created",
                "manual",
                name="triagetrigger",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("proposal", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "auto_applied",
            postgresql.ARRAY(sa.String(length=30)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=50), nullable=True),
        sa.Column("llm_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_usd", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("latency_ms", sa.Float(), server_default=sa.text("0"), nullable=False),
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
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_triage_runs_ticket_id"), "triage_runs", ["ticket_id"], unique=False)
    op.create_index(
        "uq_triage_runs_open",
        "triage_runs",
        ["ticket_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'needs_answer')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_triage_runs_open",
        table_name="triage_runs",
        postgresql_where=sa.text("status IN ('queued', 'needs_answer')"),
    )
    op.drop_index(op.f("ix_triage_runs_ticket_id"), table_name="triage_runs")
    op.drop_table("triage_runs")
