"""relabel_preview_tier

Revision ID: 0025_relabel_preview_tier
Revises: 0024_render_pod_sessions
Create Date: 2026-10-15

two-tier-renders: the `preview` tier is gone. Render runs and thread notices recorded at
it read `draft`, and a notice's code-written wording follows ("The preview …" → "The
draft …"). `render_runs.render_key` widens so a restyle variant (`variant:<id>`) can be
recorded as a rateable run. The render files are relabelled at startup, not here: this
environment does not know the render root.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025_relabel_preview_tier"
down_revision: str | None = "0024_render_pod_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE render_runs SET tier = 'draft' WHERE tier = 'preview'")
    op.execute(
        "UPDATE thread_notices SET text = 'The draft ' || substr(text, length('The preview ') + 1) "
        "WHERE tier = 'preview' AND text LIKE 'The preview %'"
    )
    op.execute("UPDATE thread_notices SET tier = 'draft' WHERE tier = 'preview'")
    op.alter_column(
        "render_runs", "render_key", type_=sa.String(96), existing_type=sa.String(32), existing_nullable=False
    )


def downgrade() -> None:
    # Which draft was once a preview cannot be recovered, so the relabel stays. Variant runs
    # (and their ratings, by cascade) do not fit the narrower key and are removed.
    op.execute("DELETE FROM render_runs WHERE length(render_key) > 32")
    op.alter_column(
        "render_runs", "render_key", type_=sa.String(32), existing_type=sa.String(96), existing_nullable=False
    )
