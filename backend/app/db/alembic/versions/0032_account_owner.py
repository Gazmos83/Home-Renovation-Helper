"""account owner: a member account's house-file rows carry its id; the owner's stay NULL

Revision ID: 0032_account_owner
Revises: 0030_drop_thread_tool_settings
Create Date: 2026-10-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0032_account_owner"
down_revision: str | None = "0030_drop_thread_tool_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The house file's root tables; every other house-file row follows one of these.
ROOT_TABLES = (
    "rooms",
    "preferences",
    "pieces",
    "model_assets",
    "compositions",
    "generator_extension_requests",
    "threads",
    "apartments",
    "remnant_sheets",
)


def upgrade() -> None:
    for table in ROOT_TABLES:
        op.add_column(table, sa.Column("owner_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_owner_id_users", table, "users", ["owner_id"], ["id"], ondelete="RESTRICT"
        )
        op.create_index(f"ix_{table}_owner_id", table, ["owner_id"])

    # Names are unique per account, not across accounts; NULL (the owner) counts as one account.
    op.drop_constraint("rooms_name_key", "rooms", type_="unique")
    op.create_unique_constraint(
        "uq_rooms_owner_name", "rooms", ["owner_id", "name"], postgresql_nulls_not_distinct=True
    )
    op.drop_constraint("apartments_name_key", "apartments", type_="unique")
    op.create_unique_constraint(
        "uq_apartments_owner_name", "apartments", ["owner_id", "name"], postgresql_nulls_not_distinct=True
    )
    op.drop_constraint("uq_compositions_scope_name", "compositions", type_="unique")
    op.create_unique_constraint(
        "uq_compositions_owner_scope_name",
        "compositions",
        ["owner_id", "scope", "name"],
        postgresql_nulls_not_distinct=True,
    )

    # A preference is keyed per account, so the key alone can no longer be the primary key.
    op.add_column(
        "preferences", sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)
    )
    op.alter_column("preferences", "id", server_default=None)
    op.drop_constraint("preferences_pkey", "preferences", type_="primary")
    op.create_primary_key("preferences_pkey", "preferences", ["id"])
    op.create_unique_constraint(
        "uq_preferences_owner_key", "preferences", ["owner_id", "key"], postgresql_nulls_not_distinct=True
    )


def downgrade() -> None:
    # A member's rows are dropped: the single-owner schema has nowhere to keep them.
    for table in ("threads", "pieces", "compositions", "rooms", "apartments", "model_assets",
                  "generator_extension_requests", "remnant_sheets", "preferences"):
        op.execute(sa.text(f"DELETE FROM {table} WHERE owner_id IS NOT NULL"))

    op.drop_constraint("uq_preferences_owner_key", "preferences", type_="unique")
    op.drop_constraint("preferences_pkey", "preferences", type_="primary")
    op.create_primary_key("preferences_pkey", "preferences", ["key"])
    op.drop_column("preferences", "id")

    op.drop_constraint("uq_compositions_owner_scope_name", "compositions", type_="unique")
    op.create_unique_constraint("uq_compositions_scope_name", "compositions", ["scope", "name"])
    op.drop_constraint("uq_apartments_owner_name", "apartments", type_="unique")
    op.create_unique_constraint("apartments_name_key", "apartments", ["name"])
    op.drop_constraint("uq_rooms_owner_name", "rooms", type_="unique")
    op.create_unique_constraint("rooms_name_key", "rooms", ["name"])

    for table in ROOT_TABLES:
        op.drop_index(f"ix_{table}_owner_id", table_name=table)
        op.drop_constraint(f"fk_{table}_owner_id_users", table, type_="foreignkey")
        op.drop_column(table, "owner_id")
