"""Which account's house file a request or a turn sees (owner-auth).

The owner's rows keep `owner_id` NULL; a member's rows carry the member's id. The
scope is set once per request (from the session cookie) or per turn (from the
graph config), never from a model argument, and then applies to every ORM query:

- every SELECT over a root table gets `owner_id IS NOT DISTINCT FROM <scope>`;
- every new root row is stamped with the scope before it is flushed.

With no scope set, the owner's house file is seen, which is what startup jobs,
scripts and the tests before member accounts expect. Child tables (versions,
reviews, uploads, notices, ...) follow their root row and are reached only through it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Final
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.db.models import (
    Apartment,
    Composition,
    GeneratorExtensionRequest,
    ModelAsset,
    Piece,
    Preference,
    RemnantSheet,
    Room,
    Thread,
)

ROOT_MODELS: Final = (
    Room,
    Preference,
    Piece,
    ModelAsset,
    Composition,
    GeneratorExtensionRequest,
    Thread,
    Apartment,
    RemnantSheet,
)

# Execution option that lifts the filter, for the few checks that must see every
# account (a package id or folder is global on disk).
ALL_ACCOUNTS: Final = "all_accounts"

_scope: ContextVar[UUID | None] = ContextVar("account_scope", default=None)


def current() -> UUID | None:
    """The member whose house file is in view, or `None` for the owner's."""
    return _scope.get()


def scope_for(user_id: UUID, *, is_owner: bool) -> UUID | None:
    return None if is_owner else user_id


@contextmanager
def scoped(member_id: UUID | None) -> Iterator[None]:
    """Run a block in one account's house file (`None` = the owner's)."""
    token = _scope.set(member_id)
    try:
        yield
    finally:
        _scope.reset(token)


def set_scope(member_id: UUID | None) -> None:
    """Set the scope for the rest of the current context (a request or a turn's thread)."""
    _scope.set(member_id)


@event.listens_for(Session, "do_orm_execute")
def _filter_by_account(state: ORMExecuteState) -> None:
    if not state.is_select or state.execution_options.get(ALL_ACCOUNTS, False):
        return
    member = _scope.get()
    state.statement = state.statement.options(
        *(
            with_loader_criteria(model, model.owner_id.is_not_distinct_from(member), include_aliases=True)
            for model in ROOT_MODELS
        )
    )


@event.listens_for(Session, "before_flush")
def _stamp_new_rows(session: Session, _context: object, _instances: object) -> None:
    member = _scope.get()
    if member is None:
        return
    for row in session.new:
        if isinstance(row, ROOT_MODELS) and row.owner_id is None:
            row.owner_id = member
