"""Immutable engineering snapshots/reports and append-only qualified method review."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0022_engineering_assessments"
down_revision = "0021_engineering_knowledge"
branch_labels = None
depends_on = None


def created():
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )


def thread():
    return sa.Column(
        "thread_id",
        sa.Uuid(),
        sa.ForeignKey("threads.id", ondelete="SET NULL"),
        nullable=True,
    )


def upgrade():
    op.create_table(
        "engineering_method_reviews",
        sa.Column("sequence", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("method_id", sa.String(64), nullable=False),
        sa.Column("method_version", sa.String(64), nullable=False),
        sa.Column("definition_hash", sa.String(64), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("reviewer", sa.String(200), nullable=False),
        sa.Column("qualification_evidence", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        created(),
        sa.CheckConstraint(
            "action IN ('pending', 'accept', 'disable')",
            name="ck_engineering_method_review_action",
        ),
    )
    op.create_table(
        "engineering_assessments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sequence", sa.Integer(), sa.Identity(), nullable=False, unique=True),
        sa.Column("package_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        thread(),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column("spec_hash", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        created(),
        sa.ForeignKeyConstraint(
            ["package_id", "version"],
            ["piece_versions.package_id", "piece_versions.version"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "id", "package_id", "version", name="uq_engineering_assessment_scope"
        ),
    )
    op.create_index(
        "ix_engineering_assessments_package_id",
        "engineering_assessments",
        ["package_id"],
    )
    op.create_table(
        "engineering_calculation_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        thread(),
        sa.Column("report", JSONB(), nullable=False),
        sa.Column("spec_hash", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        created(),
        sa.ForeignKeyConstraint(
            ["assessment_id", "package_id", "version"],
            [
                "engineering_assessments.id",
                "engineering_assessments.package_id",
                "engineering_assessments.version",
            ],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_engineering_calculation_reports_package_id",
        "engineering_calculation_reports",
        ["package_id"],
    )
    op.execute("""CREATE FUNCTION protect_engineering_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF (to_jsonb(NEW) - 'thread_id') IS DISTINCT FROM (to_jsonb(OLD) - 'thread_id')
          OR (NEW.thread_id IS DISTINCT FROM OLD.thread_id AND NEW.thread_id IS NOT NULL)
        THEN RAISE EXCEPTION 'engineering snapshots/reports are immutable'; END IF;
        RETURN NEW;
    END $$""")
    for table in ("engineering_assessments", "engineering_calculation_reports"):
        op.execute(
            f"CREATE TRIGGER immutable_snapshot BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION protect_engineering_snapshot()"
        )
    op.execute(
        "CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON engineering_method_reviews FOR EACH ROW EXECUTE FUNCTION engineering_append_only()"
    )


def downgrade():
    op.drop_table("engineering_calculation_reports")
    op.drop_table("engineering_assessments")
    op.drop_table("engineering_method_reviews")
    op.execute("DROP FUNCTION protect_engineering_snapshot()")
