"""Apply the application's Alembic migrations in-process.

The CLI (`uv run alembic upgrade head`) remains the operator command. Startup
runs the same upgrade so a new revision cannot 500 the first request after a
code reload.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine

INI: Final = Path(__file__).resolve().parents[2] / "alembic.ini"


def _config() -> Config:
    return Config(str(INI))


@contextmanager
def _database_url(database_url: str) -> Iterator[None]:
    previous = os.environ.get("ALEMBIC_DATABASE_URL")
    os.environ["ALEMBIC_DATABASE_URL"] = str(database_url)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("ALEMBIC_DATABASE_URL", None)
        else:
            os.environ["ALEMBIC_DATABASE_URL"] = previous


def head_revision() -> str | None:
    """The newest revision id in the migration scripts."""
    return ScriptDirectory.from_config(_config()).get_current_head()


def current_revision(engine: Engine) -> str | None:
    """The revision the database is at, or `None` before the first upgrade."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def upgrade_to_head(database_url: str) -> str | None:
    """Apply pending revisions to `database_url`. Returns the head revision id."""
    with _database_url(database_url):
        config = _config()
        command.upgrade(config, "head")
        return ScriptDirectory.from_config(config).get_current_head()
