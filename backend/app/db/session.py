"""Engine construction and the health probe's database check."""

from __future__ import annotations

from pydantic import PostgresDsn
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def to_sqlalchemy_url(dsn: PostgresDsn | str) -> str:
    """Pin the psycopg3 driver explicitly.

    SQLAlchemy still resolves a bare `postgresql://` URL to psycopg2, which this
    project does not install, so a bare scheme would fail at connect time with a
    missing-driver error rather than anything about the database.
    """
    raw = str(dsn)
    scheme, separator, rest = raw.partition("://")
    if not separator:
        raise ValueError(f"not a database URL: {raw!r}")
    if "+" in scheme:
        return raw
    return f"postgresql+psycopg://{rest}"


def make_engine(dsn: PostgresDsn | str, **kwargs: object) -> Engine:
    # Registers the per-account filter on every ORM session (imported here, not at
    # module top, because the models import nothing from this module's callers).
    import app.db.scope  # noqa: F401

    return create_engine(to_sqlalchemy_url(dsn), pool_pre_ping=True, **kwargs)  # type: ignore[arg-type]


def database_reachable(engine: Engine) -> bool:
    """True when a trivial query succeeds. Never raises."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    except OSError:
        return False
    return True
