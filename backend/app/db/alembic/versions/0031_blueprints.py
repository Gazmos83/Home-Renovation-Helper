"""blueprints: a confirmed plan's images kept with its apartment (render-now-blueprints-verdict-note)

Revision ID: 0031_blueprints
Revises: 0032_account_owner
Create Date: 2026-10-18
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0031_blueprints"
down_revision: str | None = "0032_account_owner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "blueprints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("apartment_id", sa.Uuid(), nullable=False),
        sa.Column("source_upload_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("original_name", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('png', 'jpeg')", name="ck_blueprints_kind"),
        sa.ForeignKeyConstraint(["apartment_id"], ["apartments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("apartment_id", "source_upload_id", name="uq_blueprints_apartment_source"),
    )
    op.create_index("ix_blueprints_apartment_id", "blueprints", ["apartment_id"])


def downgrade() -> None:
    op.drop_index("ix_blueprints_apartment_id", table_name="blueprints")
    op.drop_table("blueprints")
