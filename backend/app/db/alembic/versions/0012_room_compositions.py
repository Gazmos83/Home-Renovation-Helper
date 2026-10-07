"""room_compositions

Revision ID: 0012_room_compositions
Revises: 0011_design_uploads
Create Date: 2026-10-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012_room_compositions"
down_revision: str | None = "0011_design_uploads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("entry", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width_mm", sa.Integer(), nullable=False),
        sa.Column("depth_mm", sa.Integer(), nullable=False),
        sa.Column("height_mm", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("measured_mm", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("triangles", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('glb', 'gltf', 'obj')", name="ck_model_assets_kind"),
        sa.CheckConstraint("state IN ('checking', 'ready', 'refused')", name="ck_model_assets_state"),
        sa.CheckConstraint(
            "width_mm > 0 AND depth_mm > 0 AND height_mm > 0", name="ck_model_assets_size_positive"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "compositions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("scope IN ('room', 'apartment')", name="ck_compositions_scope"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "name", name="uq_compositions_scope_name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "composition_versions",
        sa.Column("composition_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("revised_from", sa.Integer(), nullable=True),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_composition_versions_version_positive"),
        sa.ForeignKeyConstraint(["composition_id"], ["compositions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("composition_id", "version"),
    )


def downgrade() -> None:
    op.drop_table("composition_versions")
    op.drop_table("compositions")
    op.drop_table("model_assets")
