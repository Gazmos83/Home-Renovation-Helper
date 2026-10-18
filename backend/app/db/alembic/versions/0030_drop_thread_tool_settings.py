"""drop thread_tool_settings: plugins are switched globally only (studio-navigation-tidy)

Revision ID: 0030_drop_thread_tool_settings
Revises: 0029_thread_room_declined
Create Date: 2026-10-18
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0030_drop_thread_tool_settings"
down_revision: str | None = "0029_thread_room_declined"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("thread_tool_settings")


def downgrade() -> None:
    # Recreated empty, as 0006_plugins_budgets defined it; stored choices are not restored.
    op.create_table(
        "thread_tool_settings",
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("plugin", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "btrim(plugin) <> ''", name="ck_thread_tool_settings_plugin_not_blank"
        ),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("thread_id", "plugin"),
    )
