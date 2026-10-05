"""Short-term memory: the LangGraph checkpointer (CLAUDE.md §2, §6).

Scoped to the conversation thread. The checkpointer owns its own schema and
creates it via `.setup()`; Alembic deliberately does not manage those tables —
`db/alembic/env.py` excludes them from autogenerate, so a generated migration
can never propose dropping tables it did not create.

This is a separate connection pool from the SQLAlchemy engine because the
checkpointer speaks psycopg directly. Sharing would mean handing it a
connection configured for SQLAlchemy's use, and it needs its own settings
(autocommit, no prepared statements, dict rows).
"""

from __future__ import annotations

from typing import Final

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# What PostgresSaver's own `from_conn_string` configures. Autocommit because the
# saver manages its own transactions; `prepare_threshold=0` because pooled
# connections would otherwise accumulate prepared statements across threads.
CONNECTION_KWARGS: Final = {
    "autocommit": True,
    "prepare_threshold": 0,
    "row_factory": dict_row,
}

DEFAULT_MAX_SIZE: Final = 10

# How long a caller waits for a connection from the pool. psycopg_pool defaults
# to 30 seconds, which at startup means half a minute of waiting for a database
# that is already known to be down — and the lifespan degrades rather than
# blocks, so the wait buys nothing.
DEFAULT_TIMEOUT_SECONDS: Final = 5.0


def to_psycopg_dsn(dsn: object) -> str:
    """Strip any SQLAlchemy driver suffix.

    `db/session.py` pins `postgresql+psycopg://` for SQLAlchemy's benefit;
    psycopg itself does not understand that form.
    """
    raw = str(dsn)
    scheme, separator, rest = raw.partition("://")
    if not separator:
        raise ValueError(f"not a database URL: {raw!r}")
    return f"{scheme.partition('+')[0]}://{rest}"


def make_checkpointer_pool(
    dsn: object,
    *,
    max_size: int = DEFAULT_MAX_SIZE,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
):
    """A pool configured the way the checkpointer needs its connections.

    `check`: validate a connection before handing it out. Without it, a
    database restart leaves every idle pooled connection broken, and each one
    costs a turn a failure before the pool discards it. The check is one round
    trip per checkout — cheap next to a model call.
    """
    return ConnectionPool(
        conninfo=to_psycopg_dsn(dsn),
        max_size=max_size,
        kwargs=CONNECTION_KWARGS,
        timeout=timeout,
        open=True,
        check=ConnectionPool.check_connection,
    )


def make_checkpointer(pool: ConnectionPool) -> PostgresSaver:
    """The saver over an already-open pool.

    `.setup()` is the caller's to run once at startup: it is idempotent, but it
    issues DDL, and where that happens should be visible in the lifespan rather
    than buried in a constructor.
    """
    return PostgresSaver(pool)
