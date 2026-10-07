"""version_approval

Revision ID: 0010_version_approval
Revises: 0009_remote_render_jobs
Create Date: 2026-10-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_version_approval"
down_revision: str | None = "0009_remote_render_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("piece_versions", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "uq_piece_versions_one_approved",
        "piece_versions",
        ["package_id"],
        unique=True,
        postgresql_where=sa.text("approved_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_piece_versions_one_approved", table_name="piece_versions")
    op.drop_column("piece_versions", "approved_at")
