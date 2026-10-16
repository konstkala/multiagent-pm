"""Ticket experience: new statuses, categories, assignee, points, due date, sub-tasks,
links, comments and attachments.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-17

Existing values are converted, not dropped: open→todo, resolved/closed→done;
feature→implementation, question→analysis. The free-text assignee and component columns had
no users behind them and are removed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = ("todo", "in_progress", "in_review", "done", "cancelled")
CATEGORIES = ("bug", "implementation", "improvement", "analysis", "task")


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=20)


def _created_at(default: sa.FunctionElement[sa.DateTime]) -> sa.Column[sa.DateTime]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=default, nullable=False
    )


def upgrade() -> None:
    # Status: new workflow.
    op.drop_constraint("ticketstatus", "tickets", type_="check")
    op.execute(
        "UPDATE tickets SET status = CASE status WHEN 'open' THEN 'todo' "
        "WHEN 'resolved' THEN 'done' WHEN 'closed' THEN 'done' ELSE status END"
    )
    op.alter_column("tickets", "status", server_default="todo")
    op.create_check_constraint("ticketstatus", "tickets", _in("status", STATUSES))

    # Category replaces type.
    op.add_column("tickets", sa.Column("category", sa.String(length=20)))
    op.execute(
        "UPDATE tickets SET category = CASE type WHEN 'feature' THEN 'implementation' "
        "WHEN 'question' THEN 'analysis' ELSE type END"
    )
    op.create_check_constraint("ticketcategory", "tickets", _in("category", CATEGORIES))
    op.drop_column("tickets", "type")

    op.drop_column("tickets", "component")
    op.drop_column("tickets", "assignee")
    op.add_column("tickets", sa.Column("assignee_id", sa.Uuid()))
    op.create_foreign_key(
        "tickets_assignee_id_fkey", "tickets", "users", ["assignee_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_tickets_assignee_id", "tickets", ["assignee_id"])

    op.add_column("tickets", sa.Column("story_points", sa.Integer()))
    op.create_check_constraint(
        "ck_tickets_story_points_fibonacci", "tickets", "story_points IN (1, 2, 3, 5, 8, 13)"
    )
    op.add_column("tickets", sa.Column("due_date", sa.Date()))
    op.add_column("tickets", sa.Column("parent_id", sa.Uuid()))
    op.create_foreign_key(
        "tickets_parent_id_fkey", "tickets", "tickets", ["parent_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_tickets_parent_id", "tickets", ["parent_id"])
    op.create_check_constraint("ck_tickets_not_own_parent", "tickets", "parent_id <> id")
    op.create_index("ix_tickets_project_status", "tickets", ["project_id", "status"])

    op.create_table(
        "ticket_links",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("type", _enum("linktype", "blocks", "relates_to"), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        _created_at(sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("source_id", "target_id", "type", name="uq_ticket_links"),
        sa.CheckConstraint("source_id <> target_id", name="ck_ticket_links_not_self"),
    )
    op.create_index("ix_ticket_links_source_id", "ticket_links", ["source_id"])
    op.create_index("ix_ticket_links_target_id", "ticket_links", ["target_id"])

    op.create_table(
        "ticket_comments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid()),
        sa.Column("body", sa.Text(), nullable=False),
        _created_at(sa.func.clock_timestamp()),
        sa.Column("edited_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_ticket_comments_ticket_id", "ticket_comments", ["ticket_id"])

    op.create_table(
        "ticket_attachments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("uploader_id", sa.Uuid()),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=200), nullable=False),
        _created_at(sa.func.clock_timestamp()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_ticket_attachments_ticket_id", "ticket_attachments", ["ticket_id"])


def downgrade() -> None:
    op.drop_table("ticket_attachments")
    op.drop_table("ticket_comments")
    op.drop_table("ticket_links")
    op.drop_index("ix_tickets_project_status", table_name="tickets")
    op.drop_constraint("ck_tickets_not_own_parent", "tickets", type_="check")
    op.drop_index("ix_tickets_parent_id", table_name="tickets")
    op.drop_constraint("tickets_parent_id_fkey", "tickets", type_="foreignkey")
    op.drop_column("tickets", "parent_id")
    op.drop_column("tickets", "due_date")
    op.drop_constraint("ck_tickets_story_points_fibonacci", "tickets", type_="check")
    op.drop_column("tickets", "story_points")
    op.drop_index("ix_tickets_assignee_id", table_name="tickets")
    op.drop_constraint("tickets_assignee_id_fkey", "tickets", type_="foreignkey")
    op.drop_column("tickets", "assignee_id")
    op.add_column("tickets", sa.Column("assignee", sa.String(length=100)))
    op.add_column("tickets", sa.Column("component", sa.String(length=100)))

    op.add_column("tickets", sa.Column("type", sa.String(length=20)))
    op.execute(
        "UPDATE tickets SET type = CASE category WHEN 'implementation' THEN 'feature' "
        "WHEN 'analysis' THEN 'question' WHEN 'improvement' THEN 'feature' ELSE category END"
    )
    op.create_check_constraint(
        "tickettype", "tickets", "type IN ('bug', 'feature', 'task', 'question')"
    )
    op.drop_constraint("ticketcategory", "tickets", type_="check")
    op.drop_column("tickets", "category")

    op.drop_constraint("ticketstatus", "tickets", type_="check")
    op.execute(
        "UPDATE tickets SET status = CASE status WHEN 'todo' THEN 'open' "
        "WHEN 'in_review' THEN 'in_progress' WHEN 'done' THEN 'closed' "
        "WHEN 'cancelled' THEN 'closed' ELSE status END"
    )
    op.alter_column("tickets", "status", server_default="open")
    op.create_check_constraint(
        "ticketstatus", "tickets", "status IN ('open', 'in_progress', 'resolved', 'closed')"
    )
