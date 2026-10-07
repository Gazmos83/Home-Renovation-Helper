"""room-composition: migration 0012 adds the model library and compositions, and reverses cleanly."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import make_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TABLES = {"model_assets", "compositions", "composition_versions"}


def _tables(url: str) -> set[str]:
    engine = make_engine(url)
    try:
        with Session(engine) as session:
            return set(session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).scalars())
    finally:
        engine.dispose()


def test_upgrade_and_downgrade_leave_no_drift(migrated_database: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", migrated_database)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.downgrade(config, "0011_design_uploads")
    try:
        assert not TABLES & _tables(migrated_database)
        assert "uploads" in _tables(migrated_database)
    finally:
        command.upgrade(config, "head")
    assert TABLES <= _tables(migrated_database)
    engine = make_engine(migrated_database)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()
    drift = [item for item in diff if any(t in repr(item) for t in TABLES)]
    assert drift == [], f"schema drift after upgrade/downgrade: {drift!r}"
