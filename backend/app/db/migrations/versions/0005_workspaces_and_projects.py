"""Add workspaces, projects and members; scope tickets to projects.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-17

Adds NOT NULL columns to tickets, so it fails on a non-empty tickets table instead of guessing
which project old tickets belong to.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _role(name: str, *values: str) -> sa.Column[sa.Enum]:
    return sa.Column(
        "role",
        sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=20),
        nullable=False,
    )


def _created_at() -> sa.Column[sa.DateTime]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        _role("workspacerole", "owner", "member"),
        _created_at(),
        sa.PrimaryKeyConstraint("workspace_id", "user_id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("next_ticket_number", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint("workspace_id", "key", name="uq_projects_workspace_key"),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])
    op.create_table(
        "project_members",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        _role("projectrole", "manager", "employee"),
        _created_at(),
        sa.PrimaryKeyConstraint("project_id", "user_id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])

    op.add_column("tickets", sa.Column("project_id", sa.Uuid(), nullable=False))
    op.add_column("tickets", sa.Column("number", sa.Integer(), nullable=False))
    op.add_column("tickets", sa.Column("reporter_id", sa.Uuid()))
    op.create_foreign_key(
        "tickets_project_id_fkey", "tickets", "projects", ["project_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "tickets_reporter_id_fkey", "tickets", "users", ["reporter_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_tickets_project_id", "tickets", ["project_id"])
    op.create_unique_constraint("uq_tickets_project_number", "tickets", ["project_id", "number"])


def downgrade() -> None:
    op.drop_constraint("uq_tickets_project_number", "tickets", type_="unique")
    op.drop_index("ix_tickets_project_id", table_name="tickets")
    op.drop_constraint("tickets_reporter_id_fkey", "tickets", type_="foreignkey")
    op.drop_constraint("tickets_project_id_fkey", "tickets", type_="foreignkey")
    op.drop_column("tickets", "reporter_id")
    op.drop_column("tickets", "number")
    op.drop_column("tickets", "project_id")
    op.drop_index("ix_project_members_user_id", table_name="project_members")
    op.drop_table("project_members")
    op.drop_index("ix_projects_workspace_id", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
