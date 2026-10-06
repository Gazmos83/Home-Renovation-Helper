"""reviews and review_items

Revision ID: 0005_reviews
Revises: 0006_plugins_budgets
Create Date: 2026-10-06
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_reviews"
down_revision: str | None = "0006_plugins_budgets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("renders", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _timestamp("created_at"),
        sa.CheckConstraint("btrim(package_id) <> ''", name="ck_reviews_package_id_not_blank"),
        sa.CheckConstraint("version >= 1", name="ck_reviews_version_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reviews_package_id_version", "reviews", ["package_id", "version"])
    op.create_table(
        "review_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("aspect", sa.String(length=32), nullable=False),
        sa.Column("expected", sa.Text(), nullable=False),
        sa.Column("expected_source", sa.String(length=16), nullable=False),
        sa.Column("rule_id", sa.String(length=64), nullable=True),
        sa.Column("observed", sa.Text(), nullable=False),
        sa.Column("image", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("ordinal >= 1", name="ck_review_items_ordinal_positive"),
        sa.CheckConstraint(
            "aspect IN ('brief', 'proportion', 'material', 'placement', 'construction', 'render')",
            name="ck_review_items_aspect_known",
        ),
        sa.CheckConstraint(
            "expected_source IN ('brief', 'spec', 'rule')",
            name="ck_review_items_expected_source_known",
        ),
        sa.CheckConstraint("severity IN ('minor', 'major')", name="ck_review_items_severity_known"),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')",
            name="ck_review_items_status_known",
        ),
        sa.CheckConstraint("image >= 1", name="ck_review_items_image_positive"),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_items_review_id", "review_items", ["review_id"])


def downgrade() -> None:
    op.drop_index("ix_review_items_review_id", table_name="review_items")
    op.drop_table("review_items")
    op.drop_index("ix_reviews_package_id_version", table_name="reviews")
    op.drop_table("reviews")
