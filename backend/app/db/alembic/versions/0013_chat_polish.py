"""chat_polish

Revision ID: 0013_chat_polish
Revises: 0012_room_compositions
Create Date: 2026-10-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_chat_polish"
down_revision: str | None = "0012_room_compositions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("threads", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("threads", sa.Column("summary_through", sa.String(length=64), nullable=True))
    op.add_column("model_usage", sa.Column("thread_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_model_usage_thread_id_threads",
        "model_usage",
        "threads",
        ["thread_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_model_usage_thread_id", "model_usage", ["thread_id"])
    op.drop_constraint("ck_uploads_kind", "uploads", type_="check")
    op.create_check_constraint("ck_uploads_kind", "uploads", "kind IN ('png', 'jpeg', 'design', 'text')")


def downgrade() -> None:
    # Text notes cannot satisfy the older constraint; their files stay on disk.
    op.execute(sa.text("DELETE FROM uploads WHERE kind = 'text'"))
    op.drop_constraint("ck_uploads_kind", "uploads", type_="check")
    op.create_check_constraint("ck_uploads_kind", "uploads", "kind IN ('png', 'jpeg', 'design')")
    op.drop_index("ix_model_usage_thread_id", table_name="model_usage")
    op.drop_constraint("fk_model_usage_thread_id_threads", "model_usage", type_="foreignkey")
    op.drop_column("model_usage", "thread_id")
    op.drop_column("threads", "summary_through")
    op.drop_column("threads", "summary")
