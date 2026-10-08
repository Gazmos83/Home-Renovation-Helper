"""thread_notices

Revision ID: 0015_thread_notices
Revises: 0014_conversation_rooms
Create Date: 2026-10-08
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_thread_notices"
down_revision: str | None = "0014_conversation_rooms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "thread_notices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "thread_id",
            sa.Uuid(),
            sa.ForeignKey("threads.id", ondelete="CASCADE", name="fk_thread_notices_thread_id_threads"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("after_messages", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("package_id", sa.String(length=64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.CheckConstraint("outcome IN ('succeeded', 'failed')", name="ck_thread_notices_outcome"),
    )
    op.create_index(
        "ix_thread_notices_thread_id_after_messages", "thread_notices", ["thread_id", "after_messages"]
    )


def downgrade() -> None:
    op.drop_index("ix_thread_notices_thread_id_after_messages", table_name="thread_notices")
    op.drop_table("thread_notices")
