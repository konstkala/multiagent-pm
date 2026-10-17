"""Add job priority: interactive jobs run before background ones (ADR 0018).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-17 16:10:12.402118

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("priority", sa.SmallInteger(), server_default=sa.text("10"), nullable=False),
    )
    op.drop_index("ix_jobs_runnable", table_name="jobs")
    op.create_index("ix_jobs_runnable", "jobs", ["status", "priority", "run_after"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_runnable", table_name="jobs")
    op.create_index("ix_jobs_runnable", "jobs", ["status", "run_after"], unique=False)
    op.drop_column("jobs", "priority")
