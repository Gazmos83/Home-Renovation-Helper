"""hardware_data_sheets

Revision ID: 0016_hardware_data_sheets
Revises: 0015_thread_notices
Create Date: 2026-10-08
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0016_hardware_data_sheets"
down_revision: str | None = "0015_thread_notices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hardware_data_sheets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("maker", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_kind", sa.String(length=8), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("datasheet_url", sa.Text(), nullable=True),
        sa.Column("citation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_hardware_data_sheets_key"),
        sa.CheckConstraint("btrim(key) <> ''", name="ck_hardware_data_sheets_key_not_blank"),
        sa.CheckConstraint("kind IN ('hinge', 'shelf_pin')", name="ck_hardware_data_sheets_kind_known"),
        sa.CheckConstraint("source_kind IN ('toom', 'manual')", name="ck_hardware_data_sheets_source_known"),
        sa.CheckConstraint("btrim(citation) <> ''", name="ck_hardware_data_sheets_citation_not_blank"),
    )


def downgrade() -> None:
    op.drop_table("hardware_data_sheets")
