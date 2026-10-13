"""thread_notice_revision

Revision ID: 0023_thread_notice_revision
Revises: 0022_engineering_assessments
Create Date: 2026-10-13
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023_thread_notice_revision"
down_revision: str | None = "0022_engineering_assessments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_thread_notices_kind", "thread_notices", type_="check")
    op.create_check_constraint(
        "ck_thread_notices_kind", "thread_notices", "kind IN ('render', 'build', 'revision')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM thread_notices WHERE kind = 'revision'")
    op.drop_constraint("ck_thread_notices_kind", "thread_notices", type_="check")
    op.create_check_constraint("ck_thread_notices_kind", "thread_notices", "kind IN ('render', 'build')")
