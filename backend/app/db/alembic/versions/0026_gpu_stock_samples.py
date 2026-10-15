"""gpu_stock_samples

Revision ID: 0026_gpu_stock_samples
Revises: 0025_relabel_preview_tier
Create Date: 2026-10-15
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026_gpu_stock_samples"
down_revision: str | None = "0025_relabel_preview_tier"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gpu_stock_samples",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_center", sa.String(length=32), nullable=False),
        sa.Column("gpu_type", sa.String(length=100), nullable=False),
        sa.Column("availability", sa.String(length=8), nullable=False),
        sa.CheckConstraint(
            "availability IN ('NONE', 'LOW', 'MEDIUM', 'HIGH')", name="ck_gpu_stock_samples_level_known"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gpu_stock_samples_taken_at", "gpu_stock_samples", ["taken_at"])


def downgrade() -> None:
    op.drop_index("ix_gpu_stock_samples_taken_at", table_name="gpu_stock_samples")
    op.drop_table("gpu_stock_samples")
