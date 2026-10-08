"""conversation-projects: migration 0014 upgrades, backfills, downgrades and leaves no drift;
a deleted thread clears a request's link and keeps the request."""

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
TOUCHED = ("threads", "thread_pieces", "generator_extension_requests")


def _columns(url: str, table: str) -> set[str]:
    engine = make_engine(url)
    try:
        return {column["name"] for column in inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


def _tables(url: str) -> set[str]:
    engine = make_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_backfill_moves_the_summary_to_the_build_and_downgrade_returns_it(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", migrated_database)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    engine = make_engine(migrated_database)
    bound, unbound, request_id = uuid4(), uuid4(), uuid4()
    try:
        command.downgrade(config, "0013_chat_polish")
        with Session(engine) as session:
            session.execute(
                text(
                    "INSERT INTO threads (id, title, package_id, summary, summary_through) "
                    "VALUES (:id, 'bound', 'hall-bench', 'bench decisions', 'm7')"
                ),
                {"id": bound},
            )
            session.execute(
                text(
                    "INSERT INTO threads (id, title, summary, summary_through) "
                    "VALUES (:id, 'unbound', 'general notes', 'm2')"
                ),
                {"id": unbound},
            )
            session.execute(
                text(
                    "INSERT INTO generator_extension_requests (id, field, request, status) "
                    "VALUES (:id, 'curved_front', 'a curved front', 'open')"
                ),
                {"id": request_id},
            )
            session.commit()

        command.upgrade(config, "head")
        with Session(engine) as session:
            rows = session.execute(
                text("SELECT thread_id, package_id, summary, summary_through FROM thread_pieces")
            ).all()
            mine = [row for row in rows if row.thread_id in (bound, unbound)]
            assert [(r.thread_id, r.package_id, r.summary, r.summary_through) for r in mine] == [
                (bound, "hall-bench", "bench decisions", "m7")
            ]
            threads = {
                row.id: row
                for row in session.execute(
                    text("SELECT id, summary, summary_through, room_id, apartment_id FROM threads")
                ).all()
            }
            assert threads[bound].summary is None and threads[bound].summary_through is None
            assert (threads[unbound].summary, threads[unbound].summary_through) == ("general notes", "m2")
            assert all(
                threads[t].room_id is None and threads[t].apartment_id is None
                for t in (bound, unbound)
            )
            request = session.execute(
                text("SELECT thread_id FROM generator_extension_requests WHERE id = :id"),
                {"id": request_id},
            ).one()
            assert request.thread_id is None

        command.downgrade(config, "0013_chat_polish")
        try:
            assert "thread_pieces" not in _tables(migrated_database)
            assert not {"room_id", "apartment_id"} & _columns(migrated_database, "threads")
            assert "thread_id" not in _columns(migrated_database, "generator_extension_requests")
            with Session(engine) as session:
                back = session.execute(
                    text("SELECT summary, summary_through FROM threads WHERE id = :id"),
                    {"id": bound},
                ).one()
                assert (back.summary, back.summary_through) == ("bench decisions", "m7")
        finally:
            command.upgrade(config, "head")

        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
        drift = [item for item in diff if any(name in repr(item) for name in TOUCHED)]
        assert drift == [], f"schema drift after upgrade/downgrade: {drift!r}"
    finally:
        with Session(engine) as session:
            session.execute(
                text("DELETE FROM generator_extension_requests WHERE id = :id"), {"id": request_id}
            )
            session.execute(text("DELETE FROM threads WHERE id IN (:a, :b)"), {"a": bound, "b": unbound})
            session.commit()
        engine.dispose()


def test_deleting_a_thread_keeps_its_request_without_the_link(migrated_database: str) -> None:
    engine = make_engine(migrated_database)
    thread_id, request_id = uuid4(), uuid4()
    try:
        with Session(engine) as session:
            session.execute(text("INSERT INTO threads (id, title) VALUES (:id, 'request check')"), {"id": thread_id})
            session.execute(
                text(
                    "INSERT INTO generator_extension_requests (id, field, request, status, thread_id) "
                    "VALUES (:id, 'curved_front', 'a curved front', 'open', :thread)"
                ),
                {"id": request_id, "thread": thread_id},
            )
            session.commit()
            session.execute(text("DELETE FROM threads WHERE id = :id"), {"id": thread_id})
            session.commit()
            kept = session.execute(
                text("SELECT thread_id FROM generator_extension_requests WHERE id = :id"),
                {"id": request_id},
            ).one()
            assert kept.thread_id is None
    finally:
        with Session(engine) as session:
            session.execute(
                text("DELETE FROM generator_extension_requests WHERE id = :id"), {"id": request_id}
            )
            session.execute(text("DELETE FROM threads WHERE id = :id"), {"id": thread_id})
            session.commit()
        engine.dispose()
