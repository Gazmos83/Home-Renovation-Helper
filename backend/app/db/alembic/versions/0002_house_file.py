"""house file: rooms, preferences, pieces, piece_versions, generator_extension_requests, threads

Revision ID: 0002_house_file
Revises: 0001_initial_foundation
Create Date: 2026-10-05

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_house_file"
down_revision: str | None = "0001_initial_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "rooms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("corners_mm", postgresql.JSONB(), nullable=False),
        sa.Column("height_mm", sa.Integer(), nullable=False),
        sa.Column("wall_thickness_mm", sa.Integer(), nullable=False),
        sa.Column("openings", postgresql.JSONB(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        _created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_rooms_name_not_blank"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "preferences",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "pieces",
        sa.Column("package_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=True),
        sa.Column("brief", postgresql.JSONB(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("package_id"),
    )
    op.create_table(
        "piece_versions",
        sa.Column("package_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("revised_from", sa.Integer(), nullable=True),
        sa.Column("changes", postgresql.JSONB(), nullable=False),
        _created_at(),
        sa.CheckConstraint("version >= 1", name="ck_piece_versions_version_positive"),
        sa.ForeignKeyConstraint(["package_id"], ["pieces.package_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("package_id", "version"),
    )
    op.create_table(
        "generator_extension_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.String(length=64), nullable=True),
        sa.Column("field", sa.String(length=200), nullable=False),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "threads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("package_id", sa.String(length=64), nullable=True),
        _created_at(),
        sa.Column(
            "last_turn_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("threads")
    op.drop_table("generator_extension_requests")
    op.drop_table("piece_versions")
    op.drop_table("pieces")
    op.drop_table("preferences")
    op.drop_table("rooms")
