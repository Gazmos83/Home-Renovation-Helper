"""service-foundation: the checkpointer's tables are not migration-owned.

Autogenerate runs against a database holding four tables Alembic never created,
and must propose nothing about them.
"""

from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.agent.memory.short_term import make_checkpointer, make_checkpointer_pool
from app.db.models import Base
from app.db.session import make_engine

CHECKPOINTER_TABLES = frozenset(
    {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
)


def _include_name(name, type_, parent_names) -> bool:
    return not (type_ == "table" and name in CHECKPOINTER_TABLES)


def _include_object(object_, name, type_, reflected, compare_to) -> bool:
    return not (type_ == "table" and name in CHECKPOINTER_TABLES)


@pytest.fixture
def database_with_checkpointer_tables(migrated_database: str) -> str:
    pool = make_checkpointer_pool(migrated_database)
    try:
        make_checkpointer(pool).setup()
    finally:
        pool.close()
    return migrated_database


def test_autogenerate_proposes_nothing_about_checkpointer_tables(
    database_with_checkpointer_tables: str,
) -> None:
    engine = make_engine(database_with_checkpointer_tables)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={
                    "include_name": _include_name,
                    "include_object": _include_object,
                    "compare_type": True,
                },
            )
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    rendered = repr(diff)
    for table in CHECKPOINTER_TABLES:
        assert table not in rendered, (
            f"autogenerate proposed an operation touching {table}; "
            f"Alembic must never manage the checkpointer's schema"
        )


def test_without_the_filter_autogenerate_would_propose_dropping_them(
    database_with_checkpointer_tables: str,
) -> None:
    """The filter is load-bearing, not decorative."""
    engine = make_engine(database_with_checkpointer_tables)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    rendered = repr(diff)
    assert any(table in rendered for table in CHECKPOINTER_TABLES)


def test_migrations_leave_no_drift(migrated_database: str) -> None:
    """The head schema matches the models: autogenerate finds nothing to change
    on the application's own tables."""
    engine = make_engine(migrated_database)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={
                    "include_name": _include_name,
                    "include_object": _include_object,
                    "compare_type": True,
                },
            )
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()
    assert diff == [], f"schema drift between models and migrations: {diff!r}"
