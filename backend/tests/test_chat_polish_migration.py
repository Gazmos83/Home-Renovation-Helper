"""studio-chat-polish: migration 0013 upgrades, downgrades and leaves no drift; a deleted
thread clears its usage rows' link and keeps the rows."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import make_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TOUCHED = ("threads", "model_usage", "uploads")


def _columns(url: str, table: str) -> set[str]:
    engine = make_engine(url)
    try:
        return {column["name"] for column in inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


def _insert_note(session: Session, thread_id) -> None:
    session.execute(
        text(
            "INSERT INTO uploads (id, thread_id, kind, size_bytes, original_name) "
            "VALUES (:id, :thread, 'text', 10, 'living-room.md')"
        ),
        {"id": uuid4(), "thread": thread_id},
    )


def test_upgrade_and_downgrade_leave_no_drift(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", migrated_database)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    engine = make_engine(migrated_database)
    thread_id = uuid4()
    try:
        with Session(engine) as session:
            session.execute(text("INSERT INTO threads (id, title) VALUES (:id, 'migration check')"), {"id": thread_id})
            _insert_note(session, thread_id)
            session.commit()

        command.downgrade(config, "0012_room_compositions")
        try:
            assert not {"summary", "summary_through"} & _columns(migrated_database, "threads")
            assert "thread_id" not in _columns(migrated_database, "model_usage")
            with Session(engine) as session:
                kinds = session.execute(
                    text("SELECT kind FROM uploads WHERE thread_id = :t"), {"t": thread_id}
                ).scalars().all()
                assert kinds == []
                with pytest.raises(IntegrityError):
                    _insert_note(session, thread_id)
                    session.flush()
                session.rollback()
        finally:
            command.upgrade(config, "head")

        assert {"summary", "summary_through"} <= _columns(migrated_database, "threads")
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
        drift = [item for item in diff if any(name in repr(item) for name in TOUCHED)]
        assert drift == [], f"schema drift after upgrade/downgrade: {drift!r}"
    finally:
        with Session(engine) as session:
            session.execute(text("DELETE FROM threads WHERE id = :id"), {"id": thread_id})
            session.commit()
        engine.dispose()


def test_deleting_a_thread_keeps_its_usage_without_the_link(migrated_database: str) -> None:
    engine = make_engine(migrated_database)
    thread_id, usage_id = uuid4(), uuid4()
    try:
        with Session(engine) as session:
            session.execute(text("INSERT INTO threads (id, title) VALUES (:id, 'spend check')"), {"id": thread_id})
            session.execute(
                text(
                    "INSERT INTO model_usage (id, model_id, operation, thread_id) "
                    "VALUES (:id, 'openai/gpt-5.6-luna', 'chat.foreman', :thread)"
                ),
                {"id": usage_id, "thread": thread_id},
            )
            session.commit()
            session.execute(text("DELETE FROM threads WHERE id = :id"), {"id": thread_id})
            session.commit()
            linked = session.execute(
                text("SELECT thread_id FROM model_usage WHERE id = :id"), {"id": usage_id}
            ).one()
            assert linked.thread_id is None
    finally:
        with Session(engine) as session:
            session.execute(text("DELETE FROM model_usage WHERE id = :id"), {"id": usage_id})
            session.execute(text("DELETE FROM threads WHERE id = :id"), {"id": thread_id})
            session.commit()
        engine.dispose()
