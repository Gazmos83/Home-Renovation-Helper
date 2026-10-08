"""studio-layout: migration 0015 upgrades and downgrades cleanly, leaves no drift, and
deleting a thread removes its notices."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import make_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _tables(url: str) -> set[str]:
    engine = make_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_downgrade_and_no_drift(migrated_database: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", migrated_database)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    engine = make_engine(migrated_database)
    try:
        assert "thread_notices" in _tables(migrated_database)
        command.downgrade(config, "0014_conversation_rooms")
        try:
            assert "thread_notices" not in _tables(migrated_database)
        finally:
            command.upgrade(config, "head")
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
        drift = [item for item in diff if "thread_notices" in repr(item)]
        assert drift == [], f"schema drift after upgrade/downgrade: {drift!r}"
    finally:
        engine.dispose()


def test_deleting_a_thread_removes_its_notices(migrated_database: str) -> None:
    engine = make_engine(migrated_database)
    thread_id = uuid4()
    try:
        with Session(engine) as session:
            session.execute(text("INSERT INTO threads (id, title) VALUES (:id, 'notice check')"), {"id": thread_id})
            session.execute(
                text(
                    "INSERT INTO thread_notices (id, thread_id, after_messages, outcome, tier, text) "
                    "VALUES (:id, :thread, 2, 'succeeded', 'draft', 'ready')"
                ),
                {"id": uuid4(), "thread": thread_id},
            )
            session.commit()
            session.execute(text("DELETE FROM threads WHERE id = :id"), {"id": thread_id})
            session.commit()
            left = session.execute(
                text("SELECT count(*) FROM thread_notices WHERE thread_id = :id"), {"id": thread_id}
            ).scalar_one()
            assert left == 0
    finally:
        with Session(engine) as session:
            session.execute(text("DELETE FROM threads WHERE id = :id"), {"id": thread_id})
            session.commit()
        engine.dispose()
