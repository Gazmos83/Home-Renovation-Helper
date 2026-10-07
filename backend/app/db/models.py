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

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Final
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# The width `BAAI/bge-m3` emits (CLAUDE.md §2). The `chunks` table stores it; the
# constant lives here so the model and the embedder cannot drift apart.
EMBEDDING_DIMENSIONS: Final = 1024
# The text-search configuration the corpus is indexed and searched with.
FTS_CONFIG: Final = "german"


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
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_piece_versions_version_positive"),
        # At most one approved version per piece.
        Index(
            "uq_piece_versions_one_approved",
            "package_id",
            unique=True,
            postgresql_where=text("approved_at IS NOT NULL"),
        ),
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


class RenderRun(Base):
    """One guarded render's origin (feedback-capture).

    Kept in the database, never in the version folder: the homeowner's file
    routes must not be able to reach the model or the prompt behind a render.
    """

    __tablename__ = "render_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    package_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    render_key: Mapped[str] = mapped_column(String(32), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    thread_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    slot: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        CheckConstraint("btrim(package_id) <> ''", name="ck_render_runs_package_id_not_blank"),
        CheckConstraint("version >= 1", name="ck_render_runs_version_positive"),
        CheckConstraint(
            "outcome IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_render_runs_outcome_known",
        ),
        CheckConstraint(
            "prompt IS NULL OR char_length(prompt) <= 2000", name="ck_render_runs_prompt_short"
        ),
        Index("ix_render_runs_render", "package_id", "version", "render_key"),
    )


class RenderFeedback(Base):
    """The owner's current rating of one render run: one row per run."""

    __tablename__ = "render_feedback"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("render_runs.id", ondelete="CASCADE"), primary_key=True
    )
    rating: Mapped[str] = mapped_column(String(8), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("rating IN ('up', 'down')", name="ck_render_feedback_rating_known"),
        CheckConstraint(
            "comment IS NULL OR char_length(comment) <= 1000", name="ck_render_feedback_comment_short"
        ),
    )


class RemoteRenderJob(Base):
    """One render that ran on the render server (render-offload): its numbers, for the developer."""

    __tablename__ = "remote_render_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    package_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    render_key: Mapped[str] = mapped_column(String(32), nullable=False)
    estimate_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    actual_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    transfer_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("outcome IN ('succeeded', 'failed')", name="ck_remote_render_jobs_outcome_known"),
        Index("ix_remote_render_jobs_started_at", "started_at"),
    )


# --- pricing, stores and the corpus (pricing-researcher) -----------------------------------


class SupplierPriceCategory(StrEnum):
    PANEL = "panel"
    HARDWARE = "hardware"
    FINISH = "finish"
    EDGE_BAND = "edge_band"
    CUT_SERVICE = "cut_service"
    DELIVERY = "delivery"


class SupplierPriceUnit(StrEnum):
    PER_M2 = "per_m2"
    PER_PIECE = "per_piece"
    PER_METRE = "per_metre"
    PER_CUT = "per_cut"


class Provenance(StrEnum):
    CAPTURED = "captured"
    MANUAL = "manual"
    SNAPSHOT = "snapshot"


def _in_vocabulary(column: str, vocabulary: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(member.value) for member in vocabulary)})"


class ProductSnapshot(Base):
    """A product page's details recorded by hand (the record of what the owner typed).

    Kept even after a re-record replaces the derived chunks for the same `url`.
    A snapshot never enables crawling or live lookup for its retailer.
    """

    __tablename__ = "product_snapshots"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    retailer: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    availability: Mapped[str | None] = mapped_column(Text, nullable=True)
    specification: Mapped[str] = mapped_column(Text, nullable=False)
    store_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    captured_on: Mapped[date] = mapped_column(Date, nullable=False)
    # The owner who typed it. A plain id, not a foreign key: a key to `users` would
    # make truncating the account table cascade into the price list through
    # `supplier_prices.snapshot_id`.
    recorded_by_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("btrim(retailer) <> ''", name="ck_product_snapshots_retailer_not_blank"),
        CheckConstraint("btrim(url) <> ''", name="ck_product_snapshots_url_not_blank"),
        CheckConstraint("btrim(product_name) <> ''", name="ck_product_snapshots_name_not_blank"),
        CheckConstraint(
            "btrim(specification) <> ''", name="ck_product_snapshots_specification_not_blank"
        ),
        CheckConstraint("price IS NULL OR price >= 0", name="ck_product_snapshots_price_non_negative"),
        Index("ix_product_snapshots_url_captured_on", "url", "captured_on"),
    )


class SupplierPrice(Base):
    """One price-list entry, keyed uniquely by `key`.

    `base_cents` is where the price came from (`provenance`: a fetched page, a
    hand entry or a snapshot); `override_cents` is the owner's layer on top. The
    effective price is the override when set, else the base — both stay readable.
    `unconfirmed` marks the dated planning figures seeded by the migration.
    """

    __tablename__ = "supplier_prices"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    source_site: Mapped[str] = mapped_column(String(32), nullable=False, default="toom")

    sheet_length_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sheet_width_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thickness_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bundle_length_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    base_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance: Mapped[str] = mapped_column(String(16), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("product_snapshots.id", ondelete="RESTRICT"), nullable=True
    )

    override_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    override_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    unconfirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("btrim(key) <> ''", name="ck_supplier_prices_key_not_blank"),
        CheckConstraint("btrim(label) <> ''", name="ck_supplier_prices_label_not_blank"),
        CheckConstraint(
            _in_vocabulary("category", SupplierPriceCategory), name="ck_supplier_prices_category_known"
        ),
        CheckConstraint(_in_vocabulary("unit", SupplierPriceUnit), name="ck_supplier_prices_unit_known"),
        CheckConstraint(
            _in_vocabulary("provenance", Provenance), name="ck_supplier_prices_provenance_known"
        ),
        CheckConstraint(
            "category <> 'panel' OR (sheet_width_mm IS NOT NULL "
            "AND sheet_length_mm IS NOT NULL AND thickness_mm IS NOT NULL)",
            name="ck_supplier_prices_panel_has_sheet",
        ),
        CheckConstraint(
            "base_cents IS NULL OR base_cents >= 0", name="ck_supplier_prices_base_non_negative"
        ),
        CheckConstraint(
            "override_cents IS NULL OR override_cents >= 0",
            name="ck_supplier_prices_override_non_negative",
        ),
        CheckConstraint(
            "bundle_length_mm IS NULL OR bundle_length_mm > 0",
            name="ck_supplier_prices_bundle_length_positive",
        ),
        Index("ix_supplier_prices_category", "category"),
    )

    @property
    def effective_cents(self) -> int | None:
        """Override when present, base price otherwise — never both."""
        return self.override_cents if self.override_cents is not None else self.base_cents


class Store(Base):
    """A physical store (the home store); `store_key` is the retailer's own slug."""

    __tablename__ = "stores"

    store_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_site: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # The retailer's own market identifier; null when never published, and
    # reported as such rather than answered against a default market.
    market_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("btrim(store_key) <> ''", name="ck_stores_key_not_blank"),
        CheckConstraint("btrim(url) <> ''", name="ck_stores_url_not_blank"),
    )


class StoreService(Base):
    """A cutting service at one store: whether it is performed, and its price."""

    __tablename__ = "store_services"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_key: Mapped[str] = mapped_column(
        ForeignKey("stores.store_key", ondelete="CASCADE"), nullable=False
    )
    service: Mapped[str] = mapped_column(String(64), nullable=False)
    availability: Mapped[str] = mapped_column(String(16), nullable=False)
    # Null means not established; zero means performed at no charge.
    price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("store_key", "service", name="uq_store_service"),
        CheckConstraint(
            "price_cents IS NULL OR price_cents >= 0", name="ck_store_service_price_non_negative"
        ),
    )


class StoreCutRestriction(Base):
    """A limit the owner established on site. Never touched by ingestion."""

    __tablename__ = "store_cut_restrictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_key: Mapped[str] = mapped_column(
        ForeignKey("stores.store_key", ondelete="CASCADE"), nullable=False
    )
    restriction: Mapped[str] = mapped_column(String(48), nullable=False)
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(128), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("store_key", "restriction", name="uq_store_cut_restriction"),
        CheckConstraint(
            "numeric_value IS NOT NULL OR text_value IS NOT NULL",
            name="ck_store_restriction_has_a_value",
        ),
        CheckConstraint("btrim(recorded_by) <> ''", name="ck_store_restriction_has_an_author"),
    )


class CutListPricing(Base):
    """One immutable `price_cut_list` record for a package version.

    `result` carries every line and the sheet groups; the money columns are its
    totals. It never changes after it is written — repricing makes a new row.
    """

    __tablename__ = "cut_list_pricings"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    package_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    store_key: Mapped[str] = mapped_column(ForeignKey("stores.store_key"), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    materials_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    cut_service_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    banding_cents: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    hardware_cents: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    delivery_cents: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    custom_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    undetermined_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    unpriced_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Null until chosen: `shared` (the workshop's own saw) or `per_cut` (the store tariff).
    cut_charge_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "materials_cents >= 0 AND cut_service_cents >= 0 AND banding_cents >= 0 "
            "AND hardware_cents >= 0 AND delivery_cents >= 0 AND total_cents >= 0",
            name="ck_cut_list_pricings_money_non_negative",
        ),
        CheckConstraint(
            "cut_charge_mode IS NULL OR cut_charge_mode IN ('shared', 'per_cut')",
            name="ck_cut_list_pricings_charge_mode",
        ),
        CheckConstraint(
            "custom_count >= 0 AND undetermined_count >= 0 AND review_count >= 0 "
            "AND unpriced_count >= 0",
            name="ck_cut_list_pricings_counts_non_negative",
        ),
        Index("ix_cut_list_pricings_package", "package_id", "version"),
    )


class CutListPricingEntry(Base):
    """Which price-list entries one pricing used, at the price it used.

    Exists so "a used entry cannot be deleted" is `ON DELETE RESTRICT`, a
    database fact rather than a scan of `result`.
    """

    __tablename__ = "cut_list_pricing_entries"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    pricing_id: Mapped[UUID] = mapped_column(
        ForeignKey("cut_list_pricings.id", ondelete="CASCADE"), nullable=False
    )
    entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("supplier_prices.id", ondelete="RESTRICT"), nullable=False
    )
    cents_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("pricing_id", "entry_id", name="uq_cut_list_pricing_entry"),
        Index("ix_cut_list_pricing_entries_pricing_id", "pricing_id"),
    )


class RemnantSheet(Base):
    """One row on the workshop remnant rack. Pricing never changes `quantity`."""

    __tablename__ = "remnant_sheets"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    material_key: Mapped[str] = mapped_column(String(128), nullable=False)
    length_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    width_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    grain_axis: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("btrim(material_key) <> ''", name="ck_remnant_sheets_key_not_blank"),
        CheckConstraint("length_mm > 0 AND width_mm > 0", name="ck_remnant_sheets_size_positive"),
        CheckConstraint("quantity > 0", name="ck_remnant_sheets_quantity_positive"),
        CheckConstraint("grain_axis IN ('length', 'width')", name="ck_remnant_sheets_grain_axis"),
        Index("ix_remnant_sheets_material_key", "material_key"),
    )


class Chunk(Base):
    """One embedded passage of text with its provenance (the corpus)."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)

    # Provenance: retrieval must always be able to say where an answer came from.
    source_site: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    published_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Generated and stored, so it cannot drift from `content`.
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR, Computed(f"to_tsvector('{FTS_CONFIG}', content)", persisted=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("url", "chunk_index", name="uq_chunks_url_chunk_index"),
        CheckConstraint("btrim(url) <> ''", name="ck_chunks_url_not_blank"),
        CheckConstraint("btrim(source_site) <> ''", name="ck_chunks_source_site_not_blank"),
        CheckConstraint("chunk_index >= 0", name="ck_chunks_chunk_index_non_negative"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_chunks_source_site", "source_site"),
        Index("ix_chunks_category", "category"),
    )


class GuidelineNote(Base):
    """The owner's own guideline entry: a rule or number with a required citation."""

    __tablename__ = "guideline_notes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(24), nullable=True)
    citation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("btrim(title) <> ''", name="ck_guideline_notes_title_not_blank"),
        CheckConstraint("btrim(body) <> ''", name="ck_guideline_notes_body_not_blank"),
        CheckConstraint("btrim(citation) <> ''", name="ck_guideline_notes_citation_not_blank"),
    )
