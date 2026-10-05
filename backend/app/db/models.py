"""SQLAlchemy models.

Alembic owns everything here. It does NOT own the LangGraph checkpointer's
tables — those are created by the checkpointer's own `.setup()` and are
filtered out of autogenerate in `alembic/env.py` (CLAUDE.md §2, §6).

This change ships the foundation's four tables: the single owner account, its
login sessions, the operator key/value store (model routing overrides and
generation profiles live here), and per-call model usage. Later changes add the
house file, packages, pricing and the rest.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# The width `BAAI/bge-m3` emits (CLAUDE.md §2). No table here stores a vector
# yet — the `vector` extension is enabled by the first migration so later steps
# need no separate migration for it — but the constant lives here so the model
# and any future embedding column cannot drift apart.
EMBEDDING_DIMENSIONS: Final = 1024


class Base(DeclarativeBase):
    pass


class User(Base):
    """The single owner account. The password exists here only as an argon2 hash.

    No role column: this is a single-user product (CLAUDE.md §1). Ownership is
    always resolved by the session cookie in application code, never from a
    value a caller or a model supplies.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Stored already lower-cased by application code, so the unique constraint
    # is what actually enforces "one account per address" regardless of how it
    # was typed.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        CheckConstraint("btrim(email) <> ''", name="ck_users_email_not_blank"),
    )


class AuthSession(Base):
    """One sign-in. Only the token's SHA-256 hash is stored, so a leaked table
    yields no usable cookie. The expiry slides forward while in use and the row
    can be revoked by signing out.

    A revoked row is kept rather than deleted so a stolen cookie's later use is
    still traceable.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "btrim(token_hash) <> ''", name="ck_auth_sessions_token_hash_not_blank"
        ),
        Index("ix_auth_sessions_user_id", "user_id"),
    )


class OperatorSetting(Base):
    """One operator-set value, keyed by name.

    Deliberately generic rather than a column per setting, so per-slot model
    routing overrides (`routing:<slot>`) and per-model generation profiles
    (`generation:<slug>`) share a home without another migration. An absent key
    means "use the built-in default" — application code owns that fallback.
    """

    __tablename__ = "operator_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ModelUsage(Base):
    """One row per chat-model call.

    Captured by an application-owned callback (`app/observability/usage.py`)
    that never depends on Langfuse being configured; token counts are whatever
    the gateway reported, or null when it reported none — never zero, which
    would misread as "no cost" rather than "not observed".
    """

    __tablename__ = "model_usage"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    model_id: Mapped[str] = mapped_column(String(256), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The owner who made the call. Nullable so a deleted owner does not discard
    # the spend it caused, but set on every call this single-user service makes.
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Cleared, not cascaded, when its project goes: a deleted project must not
    # silently discard the spend it caused. Nullable for the house-file step.
    project_id: Mapped[UUID | None] = mapped_column(nullable=True)
    # The Langfuse trace this call was made inside, generated by the turn before
    # the model ran. Null when tracing was off or the id could not be generated.
    trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("btrim(model_id) <> ''", name="ck_model_usage_model_id_not_blank"),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_model_usage_input_tokens_non_negative",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_model_usage_output_tokens_non_negative",
        ),
        Index("ix_model_usage_project_id", "project_id"),
    )
