"""Add profile embeddings (assignment agent, ADR 0017).

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-17 15:50:29.083774

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# No HNSW index: vectors are compared only among one project's members, never searched.
def upgrade() -> None:
    op.add_column("employee_profiles", sa.Column("embedding", Vector(384), nullable=True))
    op.add_column(
        "employee_profiles", sa.Column("embedding_model", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("employee_profiles", "embedding_model")
    op.drop_column("employee_profiles", "embedding")
