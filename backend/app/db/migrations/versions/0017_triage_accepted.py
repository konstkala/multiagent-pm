"""Add triage_runs.accepted: what the manager kept and edited (AI metrics, milestone 6).

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-17 18:01:33.207116

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "triage_runs",
        sa.Column("accepted", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("triage_runs", "accepted")
