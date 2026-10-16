"""version_verdicts and piece_versions.slot/model

Revision ID: 0027_version_verdicts
Revises: 0026_gpu_stock_samples
Create Date: 2026-10-16
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027_version_verdicts"
down_revision: str | None = "0026_gpu_stock_samples"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("piece_versions", sa.Column("slot", sa.String(length=32), nullable=True))
    op.add_column("piece_versions", sa.Column("model", sa.String(length=128), nullable=True))
    op.create_table(
        "version_verdicts",
        sa.Column("package_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=True),
        sa.Column("status_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["package_id", "version"],
            ["piece_versions.package_id", "piece_versions.version"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("verdict IN ('matches', 'mismatch')", name="ck_version_verdicts_verdict_known"),
        sa.CheckConstraint(
            "note IS NULL OR char_length(note) <= 1000", name="ck_version_verdicts_note_short"
        ),
        sa.CheckConstraint(
            "verdict <> 'mismatch' OR (note IS NOT NULL AND btrim(note) <> '')",
            name="ck_version_verdicts_mismatch_has_note",
        ),
        sa.CheckConstraint(
            "(verdict = 'matches' AND status IS NULL) OR "
            "(verdict = 'mismatch' AND status IN ('open', 'resolved', 'dismissed'))",
            name="ck_version_verdicts_status_known",
        ),
        sa.PrimaryKeyConstraint("package_id", "version"),
    )


def downgrade() -> None:
    op.drop_table("version_verdicts")
    op.drop_column("piece_versions", "model")
    op.drop_column("piece_versions", "slot")
