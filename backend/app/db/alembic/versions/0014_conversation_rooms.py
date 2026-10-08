"""conversation_rooms

Revision ID: 0014_conversation_rooms
Revises: 0013_chat_polish
Create Date: 2026-10-08
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_conversation_rooms"
down_revision: str | None = "0013_chat_polish"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("threads", sa.Column("room_id", sa.Uuid(), nullable=True))
    op.add_column("threads", sa.Column("apartment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_threads_room_id_rooms", "threads", "rooms", ["room_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_threads_apartment_id_apartments",
        "threads",
        "apartments",
        ["apartment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_threads_one_scope", "threads", "room_id IS NULL OR apartment_id IS NULL"
    )

    op.create_table(
        "thread_pieces",
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_through", sa.String(length=64), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("thread_id", "package_id"),
    )

    op.add_column(
        "generator_extension_requests", sa.Column("thread_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_generator_extension_requests_thread_id_threads",
        "generator_extension_requests",
        "threads",
        ["thread_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Backfill: a thread's bound piece becomes its first build, and the thread's
    # summary moves to that build. A thread with no bound piece keeps its summary.
    op.execute(
        sa.text(
            "INSERT INTO thread_pieces (thread_id, package_id, summary, summary_through) "
            "SELECT id, package_id, summary, summary_through FROM threads "
            "WHERE package_id IS NOT NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE threads SET summary = NULL, summary_through = NULL "
            "WHERE package_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    # Each thread gets its active build's summary back; other builds' summaries are lost.
    op.execute(
        sa.text(
            "UPDATE threads SET summary = tp.summary, summary_through = tp.summary_through "
            "FROM thread_pieces tp "
            "WHERE tp.thread_id = threads.id AND tp.package_id = threads.package_id"
        )
    )
    op.drop_constraint(
        "fk_generator_extension_requests_thread_id_threads",
        "generator_extension_requests",
        type_="foreignkey",
    )
    op.drop_column("generator_extension_requests", "thread_id")
    op.drop_table("thread_pieces")
    op.drop_constraint("ck_threads_one_scope", "threads", type_="check")
    op.drop_constraint("fk_threads_apartment_id_apartments", "threads", type_="foreignkey")
    op.drop_constraint("fk_threads_room_id_rooms", "threads", type_="foreignkey")
    op.drop_column("threads", "apartment_id")
    op.drop_column("threads", "room_id")
