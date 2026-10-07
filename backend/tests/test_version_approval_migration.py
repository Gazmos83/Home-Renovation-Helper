"""piece-first-workflow: migration 0010 adds version approval, one per piece, and reverses cleanly."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import make_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
INDEX = "uq_piece_versions_one_approved"


def _columns_and_indexes(url: str) -> tuple[set[str], set[str]]:
    engine = make_engine(url)
    try:
        with Session(engine) as session:
            columns = set(
                session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'piece_versions'"
                    )
                ).scalars()
            )
            indexes = set(
                session.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = 'piece_versions'")).scalars()
            )
        return columns, indexes
    finally:
        engine.dispose()


def test_upgrade_adds_the_column_and_the_index_and_downgrade_removes_both(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", migrated_database)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.downgrade(config, "0009_remote_render_jobs")
    try:
        columns, indexes = _columns_and_indexes(migrated_database)
        assert "approved_at" not in columns and INDEX not in indexes
    finally:
        command.upgrade(config, "head")
    columns, indexes = _columns_and_indexes(migrated_database)
    assert "approved_at" in columns and INDEX in indexes

    engine = make_engine(migrated_database)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()
    drift = [item for item in diff if "piece_versions" in repr(item)]
    assert drift == [], f"schema drift after upgrade/downgrade: {drift!r}"


def test_the_database_refuses_a_second_approved_version_of_one_piece(migrated_database: str) -> None:
    engine = make_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(
                text("INSERT INTO pieces (package_id, name, brief) VALUES ('approval-bench', 'Bench', '{}')")
            )
            for number in (1, 2):
                session.execute(
                    text(
                        "INSERT INTO piece_versions (package_id, version, changes) "
                        "VALUES ('approval-bench', :n, '[]')"
                    ),
                    {"n": number},
                )
            session.execute(
                text("UPDATE piece_versions SET approved_at = now() WHERE package_id = 'approval-bench' AND version = 1")
            )
            session.commit()
            with pytest.raises(IntegrityError):
                session.execute(
                    text(
                        "UPDATE piece_versions SET approved_at = now() "
                        "WHERE package_id = 'approval-bench' AND version = 2"
                    )
                )
            session.rollback()
            session.execute(text("DELETE FROM pieces WHERE package_id = 'approval-bench'"))
            session.commit()
    finally:
        engine.dispose()
