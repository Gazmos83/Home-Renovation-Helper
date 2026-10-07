"""render_runs and render_feedback

Revision ID: 0008_render_feedback
Revises: 0007_pricing_corpus
Create Date: 2026-10-06
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_render_feedback"
down_revision: str | None = "0007_pricing_corpus"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "render_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("render_key", sa.String(length=32), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        _timestamp("started_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("slot", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.CheckConstraint("btrim(package_id) <> ''", name="ck_render_runs_package_id_not_blank"),
        sa.CheckConstraint("version >= 1", name="ck_render_runs_version_positive"),
        sa.CheckConstraint(
            "outcome IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_render_runs_outcome_known",
        ),
        sa.CheckConstraint(
            "prompt IS NULL OR char_length(prompt) <= 2000", name="ck_render_runs_prompt_short"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_render_runs_render", "render_runs", ["package_id", "version", "render_key"]
    )
    op.create_table(
        "render_feedback",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.String(length=8), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint("rating IN ('up', 'down')", name="ck_render_feedback_rating_known"),
        sa.CheckConstraint(
            "comment IS NULL OR char_length(comment) <= 1000", name="ck_render_feedback_comment_short"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["render_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
    )


def downgrade() -> None:
    op.drop_table("render_feedback")
    op.drop_index("ix_render_runs_render", table_name="render_runs")
    op.drop_table("render_runs")
