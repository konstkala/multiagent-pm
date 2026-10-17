"""Add ticket events: status and assignee history for KPIs (ADR 0019).

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-17 17:02:41.118734

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticket_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "created",
                "status",
                "assignee",
                name="ticketeventkind",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("from_value", sa.String(length=40), nullable=True),
        sa.Column("to_value", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_events_project_kind",
        "ticket_events",
        ["project_id", "kind", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ticket_events_ticket", "ticket_events", ["ticket_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_events_ticket", table_name="ticket_events")
    op.drop_index("ix_ticket_events_project_kind", table_name="ticket_events")
    op.drop_table("ticket_events")
