"""design_uploads

Revision ID: 0011_design_uploads
Revises: 0010_version_approval
Create Date: 2026-10-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_design_uploads"
down_revision: str | None = "0010_version_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_uploads_kind", "uploads", type_="check")
    op.create_check_constraint("ck_uploads_kind", "uploads", "kind IN ('png', 'jpeg', 'design')")


def downgrade() -> None:
    # Design uploads cannot satisfy the older constraint; their files stay on disk.
    op.execute(sa.text("DELETE FROM uploads WHERE kind = 'design'"))
    op.drop_constraint("ck_uploads_kind", "uploads", type_="check")
    op.create_check_constraint("ck_uploads_kind", "uploads", "kind IN ('png', 'jpeg')")
