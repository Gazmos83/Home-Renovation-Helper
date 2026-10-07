"""design-import: migration 0011 admits design uploads and reverses cleanly."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import make_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _insert_design(session: Session, thread_id) -> None:
    session.execute(
        text(
            "INSERT INTO uploads (id, thread_id, kind, size_bytes, original_name) "
            "VALUES (:id, :thread, 'design', 10, 'wall-unit.json')"
        ),
        {"id": uuid4(), "thread": thread_id},
    )


def test_design_uploads_are_admitted_and_the_downgrade_removes_them(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", migrated_database)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    engine = make_engine(migrated_database)
    thread_id = uuid4()
    try:
        with Session(engine) as session:
            session.execute(text("INSERT INTO threads (id, title) VALUES (:id, 'migration check')"), {"id": thread_id})
            _insert_design(session, thread_id)
            session.commit()

        command.downgrade(config, "0010_version_approval")
        try:
            with Session(engine) as session:
                kinds = session.execute(
                    text("SELECT kind FROM uploads WHERE thread_id = :t"), {"t": thread_id}
                ).scalars().all()
                assert kinds == []
                with pytest.raises(IntegrityError):
                    _insert_design(session, thread_id)
                    session.flush()
                session.rollback()
        finally:
            command.upgrade(config, "head")

        with Session(engine) as session:
            _insert_design(session, thread_id)
            session.commit()
    finally:
        with Session(engine) as session:
            session.execute(text("DELETE FROM threads WHERE id = :id"), {"id": thread_id})
            session.commit()
        engine.dispose()
