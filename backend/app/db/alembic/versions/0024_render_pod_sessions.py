"""render_pod_sessions

Revision ID: 0024_render_pod_sessions
Revises: 0023_thread_notice_revision
Create Date: 2026-10-15
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024_render_pod_sessions"
down_revision: str | None = "0023_thread_notice_revision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OUTCOMES = (
    "'running', 'deleted_idle', 'deleted_manual', 'deleted_shutdown', 'orphaned', "
    "'start_failed', 'delete_failed'"
)


def upgrade() -> None:
    op.create_table(
        "render_pod_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pod_id", sa.String(length=64), nullable=False),
        sa.Column("gpu_type", sa.String(length=100), nullable=False),
        sa.Column("cost_per_hr", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("jobs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(f"outcome IN ({OUTCOMES})", name="ck_render_pod_sessions_outcome_known"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_render_pod_sessions_created_at", "render_pod_sessions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_render_pod_sessions_created_at", table_name="render_pod_sessions")
    op.drop_table("render_pod_sessions")
