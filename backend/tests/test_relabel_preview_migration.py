"""two-tier-renders: migration 0025 relabels `preview` as `draft` and widens the render key."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import make_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _config(url: str, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
    return Config(str(BACKEND_ROOT / "alembic.ini"))


def test_preview_runs_and_notices_read_draft_and_a_variant_key_fits(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(migrated_database, monkeypatch)
    engine = make_engine(migrated_database)
    run_id, thread_id = uuid4(), uuid4()
    command.downgrade(config, "0024_render_pod_sessions")
    try:
        with Session(engine) as session:
            session.execute(
                text(
                    "INSERT INTO render_runs (id, package_id, version, render_key, tier, outcome) "
                    "VALUES (:id, 'hall-bench', 2, 'turntable', 'preview', 'succeeded')"
                ),
                {"id": run_id},
            )
            session.execute(
                text("INSERT INTO render_feedback (run_id, rating, comment) VALUES (:id, 'down', 'too dark')"),
                {"id": run_id},
            )
            session.execute(text("INSERT INTO threads (id, title) VALUES (:id, 'bench')"), {"id": thread_id})
            session.execute(
                text(
                    "INSERT INTO thread_notices (id, thread_id, after_messages, outcome, kind, tier, text, "
                    "package_id, version) VALUES (:id, :thread, 1, 'succeeded', 'render', 'preview', "
                    "'The preview turntable of hall-bench version 2 is ready.', 'hall-bench', 2)"
                ),
                {"id": uuid4(), "thread": thread_id},
            )
            session.commit()
    finally:
        command.upgrade(config, "head")
    # A second upgrade to head is a no-op.
    command.upgrade(config, "head")
    try:
        with Session(engine) as session:
            run = session.execute(
                text("SELECT tier FROM render_runs WHERE id = :id"), {"id": run_id}
            ).one()
            assert run.tier == "draft"
            feedback = session.execute(
                text("SELECT rating, comment FROM render_feedback WHERE run_id = :id"), {"id": run_id}
            ).one()
            assert (feedback.rating, feedback.comment) == ("down", "too dark")
            notice = session.execute(
                text("SELECT tier, text FROM thread_notices WHERE thread_id = :id"), {"id": thread_id}
            ).one()
            assert notice.tier == "draft"
            assert notice.text == "The draft turntable of hall-bench version 2 is ready."
            key = "variant:" + "w" * 52
            session.execute(
                text(
                    "INSERT INTO render_runs (id, package_id, version, render_key, tier, outcome) "
                    "VALUES (:id, 'hall-bench', 2, :key, 'draft', 'succeeded')"
                ),
                {"id": uuid4(), "key": key},
            )
            session.commit()
    finally:
        with Session(engine) as session:
            session.execute(text("DELETE FROM render_runs WHERE package_id = 'hall-bench' AND version = 2"))
            session.execute(text("DELETE FROM threads WHERE id = :id"), {"id": thread_id})
            session.commit()
        engine.dispose()
