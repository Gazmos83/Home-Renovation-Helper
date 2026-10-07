"""remote_render_jobs

Revision ID: 0009_remote_render_jobs
Revises: 0008_render_feedback
Create Date: 2026-10-06
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_remote_render_jobs"
down_revision: str | None = "0008_render_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "remote_render_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("render_key", sa.String(length=32), nullable=False),
        sa.Column("estimate_seconds", sa.Float(), nullable=False),
        sa.Column("actual_seconds", sa.Float(), nullable=True),
        sa.Column("transfer_seconds", sa.Float(), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('succeeded', 'failed')", name="ck_remote_render_jobs_outcome_known"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remote_render_jobs_started_at", "remote_render_jobs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_remote_render_jobs_started_at", table_name="remote_render_jobs")
    op.drop_table("remote_render_jobs")
