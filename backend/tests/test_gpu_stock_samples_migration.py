"""render-gpu-availability: migration 0026 upgrades, downgrades and leaves no drift."""

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
    command.downgrade(config, "0025_relabel_preview_tier")
    try:
        assert "gpu_stock_samples" not in _tables(migrated_database)
        assert "render_pod_sessions" in _tables(migrated_database)
    finally:
        command.upgrade(config, "head")
    assert "gpu_stock_samples" in _tables(migrated_database)
    engine = make_engine(migrated_database)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()
    drift = [item for item in diff if "gpu_stock_samples" in repr(item)]
    assert drift == [], f"schema drift after upgrade/downgrade: {drift!r}"
