"""Add assignment runs (assignment agent, ADR 0017).

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-17 15:50:29.083774

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assignment_runs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "explaining",
                "ready",
                "explain_failed",
                name="assignmentstatus",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            server_default="explaining",
            nullable=False,
        ),
        sa.Column("candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("score_ms", sa.Float(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=50), nullable=True),
        sa.Column("llm_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_usd", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("latency_ms", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("chosen_user_id", sa.Uuid(), nullable=True),
        sa.Column("chosen_rank", sa.SmallInteger(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["chosen_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assignment_runs_ticket_id"), "assignment_runs", ["ticket_id"], unique=False
    )
    op.create_index(
        "uq_assignment_runs_explaining",
        "assignment_runs",
        ["ticket_id"],
        unique=True,
        postgresql_where=sa.text("status = 'explaining'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_assignment_runs_explaining",
        table_name="assignment_runs",
        postgresql_where=sa.text("status = 'explaining'"),
    )
    op.drop_index(op.f("ix_assignment_runs_ticket_id"), table_name="assignment_runs")
    op.drop_table("assignment_runs")
