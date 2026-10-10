"""dev_panel_insights: model prices and guideline uploads

Revision ID: 0019_dev_panel_insights
Revises: 0018_composition_approval
Create Date: 2026-10-10
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019_dev_panel_insights"
down_revision: str | None = "0018_composition_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_prices",
        sa.Column("slug", sa.String(length=256), primary_key=True),
        sa.Column("input_per_million", sa.Numeric(14, 6), nullable=False),
        sa.Column("output_per_million", sa.Numeric(14, 6), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("input_per_million >= 0", name="ck_model_prices_input_non_negative"),
        sa.CheckConstraint("output_per_million >= 0", name="ck_model_prices_output_non_negative"),
    )
    op.create_table(
        "guideline_uploads",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("jurisdiction", sa.String(length=200), nullable=False),
        sa.Column("published_on", sa.Date(), nullable=False),
        sa.Column("licence", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(length=200), nullable=False, unique=True),
        sa.Column("sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("btrim(title) <> ''", name="ck_guideline_uploads_title_not_blank"),
        sa.CheckConstraint("btrim(licence) <> ''", name="ck_guideline_uploads_licence_not_blank"),
        sa.CheckConstraint("size_bytes > 0", name="ck_guideline_uploads_size_positive"),
    )


def downgrade() -> None:
    # Uploaded PDFs stay on disk under the guidelines folder; only their records go.
    op.drop_table("guideline_uploads")
    op.drop_table("model_prices")
