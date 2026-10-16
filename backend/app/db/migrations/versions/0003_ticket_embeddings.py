"""Add ticket embeddings for similar-ticket search.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("embedding", Vector(384)))
    op.add_column("tickets", sa.Column("embedding_model", sa.String(length=100)))
    op.create_index(
        "ix_tickets_embedding_hnsw",
        "tickets",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_tickets_embedding_hnsw", table_name="tickets")
    op.drop_column("tickets", "embedding_model")
    op.drop_column("tickets", "embedding")
