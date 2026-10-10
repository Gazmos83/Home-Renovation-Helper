"""room-version-approval: migration 0018 adds composition version approval, one per composition, and reverses cleanly."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

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
INDEX = "uq_composition_versions_one_approved"


def _columns_and_indexes(url: str) -> tuple[set[str], set[str]]:
    engine = make_engine(url)
    try:
        with Session(engine) as session:
            columns = set(
                session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'composition_versions'"
                    )
                ).scalars()
            )
            indexes = set(
                session.execute(
                    text("SELECT indexname FROM pg_indexes WHERE tablename = 'composition_versions'")
                ).scalars()
            )
        return columns, indexes
    finally:
        engine.dispose()


def test_upgrade_adds_the_column_and_the_index_and_downgrade_removes_both(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", migrated_database)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.downgrade(config, "0017_thread_notice_kind")
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
    drift = [item for item in diff if "composition_versions" in repr(item)]
    assert drift == [], f"schema drift after upgrade/downgrade: {drift!r}"


def test_the_database_refuses_a_second_approved_version_of_one_composition(migrated_database: str) -> None:
    engine = make_engine(migrated_database)
    try:
        with Session(engine) as session:
            composition_id = uuid4()
            session.execute(
                text(
                    "INSERT INTO compositions (id, scope, name, slug) "
                    "VALUES (:id, 'room', 'Approval room', 'approval-room')"
                ),
                {"id": composition_id},
            )
            for number in (1, 2):
                session.execute(
                    text(
                        "INSERT INTO composition_versions (composition_id, version, changes) "
                        "VALUES (:id, :n, '[]')"
                    ),
                    {"id": composition_id, "n": number},
                )
            session.execute(
                text(
                    "UPDATE composition_versions SET approved_at = now() "
                    "WHERE composition_id = :id AND version = 1"
                ),
                {"id": composition_id},
            )
            session.commit()
            with pytest.raises(IntegrityError):
                session.execute(
                    text(
                        "UPDATE composition_versions SET approved_at = now() "
                        "WHERE composition_id = :id AND version = 2"
                    ),
                    {"id": composition_id},
                )
            session.rollback()
            session.execute(text("DELETE FROM compositions WHERE id = :id"), {"id": composition_id})
            session.commit()
    finally:
        engine.dispose()
