"""Shared test fixtures.

Sitting at the project root, this file is also what puts `/backend` on
`sys.path` for pytest, so `import app` resolves without the project being
installed as a package.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.session import make_engine

BACKEND_ROOT = Path(__file__).resolve().parent

TEST_FALLBACK = "postgresql://postgres:postgres@127.0.0.1:5432/home_renovation_test"

# A port nothing listens on, for the database-unreachable paths.
UNREACHABLE_DSN = "postgresql://postgres:postgres@127.0.0.1:1/home_renovation"

OWNER_EMAIL = "owner@example.com"
OWNER_PASSWORD = "an-initial-owner-password"


@pytest.fixture(autouse=True)
def dispose_engines_created_by_a_test(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Close every connection pool a test opened, when that test ends.

    Most fixtures that build an application never run the lifespan, and it is
    the lifespan that disposes `app.state.engine`. Without this, each such test
    leaves a pool of idle connections behind for the rest of the session.

    `app.main` imports `make_engine` by name, so its own reference is patched
    too. Disposing twice is safe.
    """
    from app.db import session as session_module

    created = []
    real = session_module.make_engine

    def tracked(*args: object, **kwargs: object):
        engine = real(*args, **kwargs)  # type: ignore[arg-type]
        created.append(engine)
        return engine

    monkeypatch.setattr(session_module, "make_engine", tracked)
    try:
        from app import main as main_module
    except Exception:  # noqa: BLE001  # pragma: no cover - app always imports here
        main_module = None
    if main_module is not None and hasattr(main_module, "make_engine"):
        monkeypatch.setattr(main_module, "make_engine", tracked)

    yield

    for engine in created:
        try:
            engine.dispose()
        except Exception:  # noqa: BLE001, S110 - teardown must not fail a passing test
            pass


@pytest.fixture
def test_database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL", TEST_FALLBACK)


@pytest.fixture
def settings(test_database_url: str) -> Settings:
    """Settings built from explicit values, never from the ambient environment.

    The gateway probe is disabled so a `TestClient` that runs the lifespan does
    not contact OpenRouter; a test that wants the probe builds its own settings.
    """
    return Settings(
        database_url=test_database_url,
        test_database_url=test_database_url,
        openrouter_api_key="sk-or-test-not-a-real-key",
        cors_origins="http://localhost:5173",
        owner_email=OWNER_EMAIL,
        owner_password=OWNER_PASSWORD,
        gateway_probe_enabled=False,
        _env_file=None,
    )


@pytest.fixture
def render_root(tmp_path: Path) -> Path:
    """An empty render root, so no test writes under `docs/renders`."""
    root = tmp_path / "renders"
    root.mkdir()
    return root


@pytest.fixture
def fake_blender(tmp_path: Path) -> Path:
    """An executable stand-in, so `generation_enabled` is true without Blender."""
    binary = tmp_path / "blender"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    return binary


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove every variable Settings reads, so absence is really absence."""
    for name in (
        "DATABASE_URL",
        "TEST_DATABASE_URL",
        "OPENROUTER_API_KEY",
        "CORS_ORIGINS",
        "OWNER_EMAIL",
        "OWNER_PASSWORD",
        "DEV_PANEL_ENABLED",
        "GATEWAY_PROBE_ENABLED",
        "SESSION_COOKIE_SECURE",
        "LANGFUSE_HOST",
        "LANGFUSE_BASE_URL",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "BLENDER_BIN",
        "BLENDER_TIMEOUT_SECONDS",
        "RENDER_ROOT",
    ):
        monkeypatch.delenv(name, raising=False)
    yield


@pytest.fixture(scope="session")
def migrated_database() -> str:
    """Bring the test database to head once per run.

    Skips the whole database-backed suite when Postgres is not up, so a
    developer without Docker running gets a clear skip rather than a wall of
    connection errors.
    """
    url = os.environ.get("TEST_DATABASE_URL", TEST_FALLBACK)
    engine = make_engine(url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as error:  # noqa: BLE001 - any failure means unavailable
        pytest.skip(f"test database unavailable at {url}: {type(error).__name__}")
    finally:
        engine.dispose()

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    previous = os.environ.get("ALEMBIC_DATABASE_URL")
    os.environ["ALEMBIC_DATABASE_URL"] = url
    try:
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("ALEMBIC_DATABASE_URL", None)
        else:
            os.environ["ALEMBIC_DATABASE_URL"] = previous
    return url


@pytest.fixture
def db_session(migrated_database: str) -> Iterator[Session]:
    """A session over the migrated test database."""
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        yield session
        session.rollback()
    engine.dispose()


def embedding(seed: int, *, magnitude: float = 1.0) -> list[float]:
    """A one-hot vector of the provisioned width.

    One-hot keeps cosine similarity trivial to reason about in assertions:
    identical vectors score 1.0, different positions score 0.0. A zero vector
    would leave cosine distance undefined, so `magnitude` is never 0.
    """
    from app.db.models import EMBEDDING_DIMENSIONS

    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[seed % EMBEDDING_DIMENSIONS] = magnitude
    return vector


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="run tests that call the real OpenRouter gateway (spends money)",
    )
    parser.addoption(
        "--blender",
        action="store_true",
        default=False,
        help="run tests that invoke the pinned local Blender 5.2.1 LTS binary",
    )


@pytest.fixture(scope="session")
def blender_bin() -> Path:
    """The pinned local Blender, used only by opt-in `blender` tests."""
    configured = os.environ.get(
        "BLENDER_BIN", "/home/pingu/Applications/blender-5.2.1-linux-x64/blender"
    )
    binary = Path(configured)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        pytest.skip(f"BLENDER_BIN is not an executable file: {binary}")
    result = subprocess.run(
        [str(binary), "--version"], text=True, capture_output=True, timeout=30, check=False
    )
    if result.stdout.splitlines()[0:1] != ["Blender 5.2.1 LTS"]:
        pytest.skip(f"BLENDER_BIN must be Blender 5.2.1 LTS: {result.stdout.strip()}")
    return binary


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip external-service tests unless explicitly asked for.

    A hook rather than a default `-m` in pyproject: any `-m` on the command
    line replaces `addopts`' one outright, so `-m "not slow"` would have
    silently re-enabled billing.
    """
    live = config.getoption("--live")
    blender = config.getoption("--blender")
    for item in items:
        if "blender" in item.keywords and not blender:
            item.add_marker(pytest.mark.skip(reason="needs --blender and Blender 5.2.1 LTS"))
        if "live" in item.keywords and not live:
            item.add_marker(pytest.mark.skip(reason="needs --live and an OpenRouter key"))
