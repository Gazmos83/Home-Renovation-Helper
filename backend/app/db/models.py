"""SQLAlchemy models.

Alembic owns everything here. It does NOT own the LangGraph checkpointer's
tables — those are created by the checkpointer's own `.setup()` and are
filtered out of autogenerate in `alembic/env.py` (CLAUDE.md §2, §6).

The foundation's four tables: the single owner account, its login sessions, the
operator key/value store (model routing overrides and generation profiles live
here), and per-call model usage. The house file (rooms, preferences, pieces and
their versions, generator-extension requests, the thread index) follows. Later
changes add pricing and the rest.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
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
    # Pre-call count written by the budget step. Used when the gateway reported
    # no token figures, so the daily ceiling still has a number to add.
    estimated_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
        CheckConstraint(
            "estimated_tokens IS NULL OR estimated_tokens >= 0",
            name="ck_model_usage_estimated_tokens_non_negative",
        ),
        Index("ix_model_usage_project_id", "project_id"),
        Index("ix_model_usage_model_id_created_at", "model_id", "created_at"),
    )


class Room(Base):
    """One measured room of the owner's home (house file).

    The corners, openings and heights are what Intake's confirmed numbers say;
    they are validated like a room-scene document before they are stored.
    """

    __tablename__ = "rooms"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    corners_mm: Mapped[list] = mapped_column(JSONB, nullable=False)
    height_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    wall_thickness_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    openings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # When set, the corners are in the apartment's plan frame.
    apartment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("apartments.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="ck_rooms_name_not_blank"),
    )


class Preference(Base):
    """A named style or default value (`style`, `budget_eur`, ...)."""

    __tablename__ = "preferences"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Piece(Base):
    """A piece the owner confirmed, one per package id."""

    __tablename__ = "pieces"

    package_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    room_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True
    )
    brief: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PieceVersion(Base):
    """A version record mirroring a `docs/renders/<id>/v<N>` folder."""

    __tablename__ = "piece_versions"

    package_id: Mapped[str] = mapped_column(
        ForeignKey("pieces.package_id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    revised_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_piece_versions_version_positive"),
    )


class GeneratorExtensionRequest(Base):
    """A change the schema cannot express yet (ladder step 2, CLAUDE.md §3)."""

    __tablename__ = "generator_extension_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    package_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    field: Mapped[str] = mapped_column(String(200), nullable=False)
    request: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Thread(Base):
    """The index of one conversation; its messages live in the checkpointer."""

    __tablename__ = "threads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    package_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_turn_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Apartment(Base):
    """A group of rooms measured in one plan frame (millimetres)."""

    __tablename__ = "apartments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    ceiling_height_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    wall_thickness_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="ck_apartments_name_not_blank"),
    )


class Upload(Base):
    """An image the owner attached to a conversation. Only its metadata lives
    here; the bytes are a file under the upload root."""

    __tablename__ = "uploads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    thread_id: Mapped[UUID] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    original_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("kind IN ('png', 'jpeg')", name="ck_uploads_kind"),
        Index("ix_uploads_thread_id", "thread_id"),
    )


class ThreadToolSetting(Base):
    """Per-conversation on/off for one plugin. Absent means the manifest default."""

    __tablename__ = "thread_tool_settings"

    thread_id: Mapped[UUID] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), primary_key=True
    )
    plugin: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("btrim(plugin) <> ''", name="ck_thread_tool_settings_plugin_not_blank"),
    )


class PluginOutcome(StrEnum):
    """How one HTTPS plugin invocation ended; the audit trail keeps no payload."""

    OK = "ok"
    REFUSED = "refused"
    TIMEOUT = "timeout"
    TOO_LARGE = "too_large"
    INVALID_OUTPUT = "invalid_output"
    UNFETCHABLE = "unfetchable"


class PluginInvocation(Base):
    """One HTTPS plugin call's outcome — no arguments and no response body."""

    __tablename__ = "plugin_invocations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plugin: Mapped[str] = mapped_column(String(64), nullable=False)
    thread_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("threads.id", ondelete="SET NULL"), nullable=True
    )
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("btrim(plugin) <> ''", name="ck_plugin_invocations_plugin_not_blank"),
        CheckConstraint(
            "outcome IN ('ok', 'refused', 'timeout', 'too_large', 'invalid_output', 'unfetchable')",
            name="ck_plugin_invocations_outcome_known",
        ),
        Index("ix_plugin_invocations_plugin", "plugin"),
        Index("ix_plugin_invocations_thread_id", "thread_id"),
    )


class Review(Base):
    """One Reviewer's check of a package version against its spec and brief."""

    __tablename__ = "reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    package_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    renders: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("btrim(package_id) <> ''", name="ck_reviews_package_id_not_blank"),
        CheckConstraint("version >= 1", name="ck_reviews_version_positive"),
        Index("ix_reviews_package_id_version", "package_id", "version"),
    )


class ReviewItem(Base):
    """One discrepancy on a review. Status is open until the owner closes it."""

    __tablename__ = "review_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    aspect: Mapped[str] = mapped_column(String(32), nullable=False)
    expected: Mapped[str] = mapped_column(Text, nullable=False)
    expected_source: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observed: Mapped[str] = mapped_column(Text, nullable=False)
    image: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("ordinal >= 1", name="ck_review_items_ordinal_positive"),
        CheckConstraint(
            "aspect IN ('brief', 'proportion', 'material', 'placement', 'construction', 'render')",
            name="ck_review_items_aspect_known",
        ),
        CheckConstraint(
            "expected_source IN ('brief', 'spec', 'rule')",
            name="ck_review_items_expected_source_known",
        ),
        CheckConstraint("severity IN ('minor', 'major')", name="ck_review_items_severity_known"),
        CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')",
            name="ck_review_items_status_known",
        ),
        CheckConstraint("image >= 1", name="ck_review_items_image_positive"),
        Index("ix_review_items_review_id", "review_id"),
    )
