"""Versioned engineering sources, evidence and append-only rights decisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

revision: str = "0021_engineering_knowledge"
down_revision: str | None = "0020_summary_owner_edited"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), primary_key=True)


def _version() -> sa.Column:
    return sa.Column(
        "version_id",
        sa.Uuid(),
        sa.ForeignKey("knowledge_source_versions.id"),
        nullable=False,
    )


def _created() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        _id(),
        sa.Column("key", sa.String(120), nullable=False, unique=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("publisher", sa.String(300)),
        sa.Column("source_url", sa.Text()),
        _created(),
    )
    op.create_table(
        "knowledge_source_versions",
        _id(),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_sources.id"),
            nullable=False,
        ),
        sa.Column("edition", sa.String(200)),
        sa.Column("attributes", pg.JSONB(), nullable=False),
        sa.Column("collections", pg.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("local_path", sa.Text()),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False),
        sa.Column("reviewed_by", sa.String(200)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "superseded_by", sa.Uuid(), sa.ForeignKey("knowledge_source_versions.id")
        ),
        _created(),
    )
    op.create_table(
        "knowledge_rights_decisions",
        sa.Column("sequence", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id", sa.Uuid(), nullable=False, unique=True),
        _version(),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("grants", pg.JSONB(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("reviewer", sa.String(200), nullable=False),
        sa.Column("use_context", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        _created(),
        sa.CheckConstraint(
            "action IN ('approve', 'revoke')", name="ck_knowledge_rights_action"
        ),
    )
    op.create_index(
        "ix_knowledge_rights_decisions_version_id",
        "knowledge_rights_decisions",
        ["version_id"],
    )
    op.execute("""
        CREATE FUNCTION engineering_append_only() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'engineering rights decisions are append-only'; END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER knowledge_rights_append_only BEFORE UPDATE OR DELETE ON knowledge_rights_decisions
        FOR EACH ROW EXECUTE FUNCTION engineering_append_only();
        CREATE FUNCTION engineering_version_identity() RETURNS trigger AS $$
        BEGIN
          IF NEW.source_id IS DISTINCT FROM OLD.source_id OR NEW.edition IS DISTINCT FROM OLD.edition
             OR NEW.attributes IS DISTINCT FROM OLD.attributes OR NEW.collections IS DISTINCT FROM OLD.collections
             OR (OLD.content_hash IS NOT NULL AND NEW.content_hash IS DISTINCT FROM OLD.content_hash)
          THEN RAISE EXCEPTION 'engineering source version identity is immutable'; END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER knowledge_version_identity BEFORE UPDATE ON knowledge_source_versions
        FOR EACH ROW EXECUTE FUNCTION engineering_version_identity();
    """)
    op.create_table(
        "engineering_chunks",
        _id(),
        _version(),
        sa.Column("block_id", sa.String(120), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("provenance", pg.JSONB(), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column(
            "search_vector",
            pg.TSVECTOR(),
            sa.Computed(
                "to_tsvector('german', content) || to_tsvector('english', content) || to_tsvector('simple', content)",
                persisted=True,
            ),
        ),
        sa.UniqueConstraint(
            "version_id", "block_id", name="uq_engineering_chunk_block"
        ),
    )
    op.create_index(
        "ix_engineering_chunks_version_id", "engineering_chunks", ["version_id"]
    )
    op.create_index(
        "ix_engineering_chunks_fts",
        "engineering_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_engineering_chunks_vector",
        "engineering_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_table(
        "engineering_properties",
        _id(),
        _version(),
        sa.Column("block_id", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("record", pg.JSONB(), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False),
        sa.Column("reviewed_by", sa.String(200)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        _created(),
    )
    op.create_index(
        "ix_engineering_properties_version_id", "engineering_properties", ["version_id"]
    )
    op.create_table(
        "knowledge_ingestion_runs",
        _id(),
        _version(),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("blocks", sa.Integer(), nullable=False),
        sa.Column("reused_vectors", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text()),
        _created(),
    )
    op.create_table(
        "engineering_evidence_uses",
        _id(),
        sa.Column(
            "thread_id",
            sa.Uuid(),
            sa.ForeignKey("threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _version(),
        sa.Column("block_id", sa.String(120), nullable=False),
        sa.Column("qualifications", pg.JSONB(), nullable=False),
        _created(),
    )
    op.create_index(
        "ix_engineering_evidence_uses_thread_id",
        "engineering_evidence_uses",
        ["thread_id"],
    )


def downgrade() -> None:
    for table in (
        "engineering_evidence_uses",
        "knowledge_ingestion_runs",
        "engineering_properties",
        "engineering_chunks",
        "knowledge_rights_decisions",
        "knowledge_source_versions",
        "knowledge_sources",
    ):
        op.drop_table(table)
    op.execute(
        "DROP FUNCTION engineering_append_only(); DROP FUNCTION engineering_version_identity();"
    )
