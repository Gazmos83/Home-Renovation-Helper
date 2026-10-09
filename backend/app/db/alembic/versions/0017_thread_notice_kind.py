"""thread_notice_kind

Revision ID: 0017_thread_notice_kind
Revises: 0016_hardware_data_sheets
Create Date: 2026-10-09
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_thread_notice_kind"
down_revision: str | None = "0016_hardware_data_sheets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "thread_notices",
        sa.Column("kind", sa.String(length=8), nullable=False, server_default="render"),
    )
    op.create_check_constraint("ck_thread_notices_kind", "thread_notices", "kind IN ('render', 'build')")
    op.alter_column("thread_notices", "tier", existing_type=sa.String(length=16), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM thread_notices WHERE kind = 'build'")
    op.alter_column("thread_notices", "tier", existing_type=sa.String(length=16), nullable=False)
    op.drop_constraint("ck_thread_notices_kind", "thread_notices", type_="check")
    op.drop_column("thread_notices", "kind")
