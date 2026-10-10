"""summary_owner_edited: the owner's corrected conversation notes

Revision ID: 0020_summary_owner_edited
Revises: 0019_dev_panel_insights
Create Date: 2026-10-10
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020_summary_owner_edited"
down_revision: str | None = "0019_dev_panel_insights"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("threads", "thread_pieces"):
        op.add_column(
            table,
            sa.Column("summary_owner_edited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )


def downgrade() -> None:
    for table in ("thread_pieces", "threads"):
        op.drop_column(table, "summary_owner_edited")
