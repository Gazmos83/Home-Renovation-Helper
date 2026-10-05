"""apartments, uploads, rooms.apartment_id

Revision ID: 0003_apartments_uploads
Revises: 0002_house_file
Create Date: 2026-10-06

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_apartments_uploads"
down_revision: str | None = "0002_house_file"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "apartments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("ceiling_height_mm", sa.Integer(), nullable=False),
        sa.Column("wall_thickness_mm", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_apartments_name_not_blank"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=512), nullable=False),
        _timestamp("created_at"),
        sa.CheckConstraint("kind IN ('png', 'jpeg')", name="ck_uploads_kind"),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uploads_thread_id", "uploads", ["thread_id"])
    op.add_column("rooms", sa.Column("apartment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_rooms_apartment_id", "rooms", "apartments", ["apartment_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_rooms_apartment_id", "rooms", type_="foreignkey")
    op.drop_column("rooms", "apartment_id")
    op.drop_index("ix_uploads_thread_id", table_name="uploads")
    op.drop_table("uploads")
    op.drop_table("apartments")
