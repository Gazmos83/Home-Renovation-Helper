"""thread_room_renders and thread_notices.composition_slug/render_key

Revision ID: 0028_room_render_notices
Revises: 0027_version_verdicts
Create Date: 2026-10-16
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028_room_render_notices"
down_revision: str | None = "0027_version_verdicts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("thread_notices", sa.Column("composition_slug", sa.String(length=64), nullable=True))
    op.add_column("thread_notices", sa.Column("render_key", sa.String(length=96), nullable=True))
    op.create_table(
        "thread_room_renders",
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("composition_slug", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("render_key", sa.String(length=96), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["threads.id"], ondelete="CASCADE", name="fk_thread_room_renders_thread_id_threads"
        ),
        sa.PrimaryKeyConstraint("thread_id", "composition_slug", "version", "render_key"),
    )


def downgrade() -> None:
    op.drop_table("thread_room_renders")
    op.drop_column("thread_notices", "render_key")
    op.drop_column("thread_notices", "composition_slug")
