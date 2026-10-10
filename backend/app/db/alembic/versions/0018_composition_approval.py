"""composition_approval

Revision ID: 0018_composition_approval
Revises: 0017_thread_notice_kind
Create Date: 2026-10-10
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_composition_approval"
down_revision: str | None = "0017_thread_notice_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "composition_versions", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "uq_composition_versions_one_approved",
        "composition_versions",
        ["composition_id"],
        unique=True,
        postgresql_where=sa.text("approved_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_composition_versions_one_approved", table_name="composition_versions")
    op.drop_column("composition_versions", "approved_at")
