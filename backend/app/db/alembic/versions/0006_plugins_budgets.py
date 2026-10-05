"""plugins and token budgets: thread_tool_settings, plugin_invocations, estimated_tokens

Revision ID: 0006_plugins_budgets
Revises: 0003_apartments_uploads
Create Date: 2026-10-06

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_plugins_budgets"
down_revision: str | None = "0003_apartments_uploads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "thread_tool_settings",
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("plugin", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            "btrim(plugin) <> ''", name="ck_thread_tool_settings_plugin_not_blank"
        ),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("thread_id", "plugin"),
    )
    op.create_table(
        "plugin_invocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plugin", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        _timestamp("created_at"),
        sa.CheckConstraint(
            "btrim(plugin) <> ''", name="ck_plugin_invocations_plugin_not_blank"
        ),
        sa.CheckConstraint(
            "outcome IN ('ok', 'refused', 'timeout', 'too_large', 'invalid_output', 'unfetchable')",
            name="ck_plugin_invocations_outcome_known",
        ),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plugin_invocations_plugin", "plugin_invocations", ["plugin"])
    op.create_index("ix_plugin_invocations_thread_id", "plugin_invocations", ["thread_id"])
    op.add_column("model_usage", sa.Column("estimated_tokens", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_model_usage_estimated_tokens_non_negative",
        "model_usage",
        "estimated_tokens IS NULL OR estimated_tokens >= 0",
    )
    op.create_index(
        "ix_model_usage_model_id_created_at", "model_usage", ["model_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_model_usage_model_id_created_at", table_name="model_usage")
    op.drop_constraint("ck_model_usage_estimated_tokens_non_negative", "model_usage", type_="check")
    op.drop_column("model_usage", "estimated_tokens")
    op.drop_index("ix_plugin_invocations_thread_id", table_name="plugin_invocations")
    op.drop_index("ix_plugin_invocations_plugin", table_name="plugin_invocations")
    op.drop_table("plugin_invocations")
    op.drop_table("thread_tool_settings")
