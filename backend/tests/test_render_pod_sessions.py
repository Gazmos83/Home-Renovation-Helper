"""render-pod-lifecycle: migration 0024 and the developer's list of pod sessions."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Base, RenderPodSession
from app.db.session import make_engine
from app.render.offload import sessions

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def engine(migrated_database: str) -> Iterator:
    engine = make_engine(migrated_database)

    def clear() -> None:
        with Session(engine) as session:
            session.execute(text("DELETE FROM render_pod_sessions"))
            session.commit()

    clear()
    yield engine
    clear()
    engine.dispose()


def _tables(url: str) -> set[str]:
    engine = make_engine(url)
    try:
        with Session(engine) as session:
            return set(
                session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).scalars()
            )
    finally:
        engine.dispose()


def test_upgrade_and_downgrade_leave_no_drift(migrated_database: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", migrated_database)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.downgrade(config, "0023_thread_notice_revision")
    try:
        assert "render_pod_sessions" not in _tables(migrated_database)
        assert "remote_render_jobs" in _tables(migrated_database)
    finally:
        command.upgrade(config, "head")
    assert "render_pod_sessions" in _tables(migrated_database)
    engine = make_engine(migrated_database)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()
    drift = [item for item in diff if "render_pod_sessions" in repr(item)]
    assert drift == [], f"schema drift after upgrade/downgrade: {drift!r}"


def test_a_session_runs_from_creation_to_deletion_with_its_cost(engine) -> None:
    session_id = sessions.open_session(engine, "pod1", "NVIDIA GeForce RTX 4090", 0.69)
    sessions.update_session(engine, session_id, jobs=1)
    sessions.update_session(engine, session_id, jobs=1)
    with Session(engine) as db:
        row = db.get(RenderPodSession, session_id)
        row.created_at = datetime.now(UTC) - timedelta(minutes=30)
        db.commit()
    sessions.close_session(engine, session_id, "deleted_idle")
    with Session(engine) as db:
        [listed] = sessions.recent_sessions(db)
    assert listed["outcome"] == "deleted_idle" and listed["jobs"] == 2
    assert 1790 <= listed["lifetime_seconds"] <= 1810
    assert listed["cost_usd"] == pytest.approx(0.35, abs=0.01)


def test_an_orphan_is_one_closed_session(engine) -> None:
    sessions.record_orphan(engine, "pod9", "NVIDIA GeForce RTX 4090", None)
    with Session(engine) as db:
        [listed] = sessions.recent_sessions(db)
    assert listed["outcome"] == "orphaned" and listed["deleted_at"] is not None
    assert listed["cost_usd"] is None


def test_recording_never_raises(engine) -> None:
    sessions.update_session(engine, None, jobs=1)
    sessions.close_session(engine, None, "deleted_idle")
    sessions.update_session(engine, sessions.open_session(engine, "pod1", "x", None), outcome="not-an-outcome")
