"""Backfill ticket events from the tickets' current state (data migration, ADR 0019).

Approximate by design: tickets only knew their creation time, current status and last update.
Each gets "created" at created_at, its current status (if not To do) at updated_at, and its
current assignee at created_at. Dashboards say history before this migration is approximate.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-17 17:05:12.502931

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO ticket_events (ticket_id, project_id, actor_id, kind, created_at) "
        "SELECT id, project_id, reporter_id, 'created', created_at FROM tickets"
    )
    op.execute(
        "INSERT INTO ticket_events (ticket_id, project_id, kind, from_value, to_value, created_at) "
        "SELECT id, project_id, 'status', 'todo', status, updated_at FROM tickets "
        "WHERE status <> 'todo'"
    )
    op.execute(
        "INSERT INTO ticket_events (ticket_id, project_id, kind, to_value, created_at) "
        "SELECT id, project_id, 'assignee', assignee_id::text, created_at FROM tickets "
        "WHERE assignee_id IS NOT NULL"
    )


def downgrade() -> None:
    # Rolling back means "before history existed": real events recorded since go too.
    op.execute("DELETE FROM ticket_events")
