"""service-foundation: the checkpointer's schema exists once the service is up."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import Settings
from app.db.session import make_engine
from app.main import create_app
from conftest import OWNER_EMAIL, OWNER_PASSWORD, UNREACHABLE_DSN

CHECKPOINTER_TABLES = frozenset(
    {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
)


def _settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        owner_email=OWNER_EMAIL,
        owner_password=OWNER_PASSWORD,
        gateway_probe_enabled=False,
        _env_file=None,
    )


def test_startup_creates_the_checkpointer_schema(migrated_database: str) -> None:
    engine = make_engine(migrated_database)
    try:
        with engine.begin() as connection:
            for table in CHECKPOINTER_TABLES:
                connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))

        with TestClient(create_app(_settings(migrated_database))) as client:
            assert client.get("/health").status_code == 200

        with engine.connect() as connection:
            present = {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = current_schema()"
                    )
                )
            }
        for table in CHECKPOINTER_TABLES:
            assert table in present
    finally:
        engine.dispose()


def test_a_second_startup_is_harmless(migrated_database: str) -> None:
    """`.setup()` runs on every boot, so booting twice must not fail."""
    for _ in range(2):
        with TestClient(create_app(_settings(migrated_database))) as client:
            assert client.get("/health").status_code == 200


def test_the_checkpointer_is_reachable_from_app_state(migrated_database: str) -> None:
    app = create_app(_settings(migrated_database))
    with TestClient(app):
        assert app.state.checkpointer is not None
        assert app.state.checkpointer_pool is not None


def test_an_unreachable_database_does_not_stop_startup() -> None:
    app = create_app(_settings(UNREACHABLE_DSN))
    with TestClient(app) as client:
        assert client.get("/health").status_code == 503
        assert app.state.checkpointer is None
