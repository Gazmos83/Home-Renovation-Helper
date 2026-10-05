"""FastAPI entrypoint.

The foundation: configuration, structured logging, the migration-owned schema's
engine, the conversation checkpointer, the single owner account, per-agent model
routing, the startup gateway probe, optional Langfuse tracing, the auth and
health routers, and outermost CORS. Later changes (house file, agents, pricing,
the Blender tools) attach to this app rather than replacing it.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import logging as app_logging
from app.agent.memory.short_term import make_checkpointer, make_checkpointer_pool
from app.agent.models.probe import probe_models
from app.agent.models.profiles import Profiles
from app.agent.models.routing import load_routing, read_routing_overrides
from app.api.admin_render import router as admin_render_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.limits import RateLimiter
from app.api.packages import router as packages_router
from app.api.renders import router as renders_router
from app.auth.accounts import ensure_owner
from app.blender import storage
from app.config import Settings, get_settings
from app.db.session import make_engine
from app.observability.langfuse import Tracing
from app.render.approvals import ApprovalStore
from app.render.benchmark_store import read_benchmark
from app.render.tiers import load_tiers


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings: Settings = app.state.settings

    # The checkpointer owns its own schema and creates it here (§6). `.setup()`
    # is idempotent, so every boot runs it. An unreachable database leaves the
    # agent without a checkpointer rather than silently forgetting conversations
    # — /health is what reports the database, and a later turn that needs the
    # checkpointer refuses with a stated reason.
    app.state.checkpointer_pool = None
    app.state.checkpointer = None
    try:
        pool = make_checkpointer_pool(settings.database_url)
        checkpointer = make_checkpointer(pool)
        checkpointer.setup()
    except Exception as error:  # noqa: BLE001 - reported, not fatal
        app_logging.logger.warning(
            "conversation checkpointer unavailable at startup: %s", type(error).__name__
        )
    else:
        app.state.checkpointer_pool = pool
        app.state.checkpointer = checkpointer

    # The single owner, created from configuration when the account table is
    # empty and never overwritten afterwards (owner-auth). A weak configured
    # password is already refused by configuration validation; this is where it
    # is first used. An unreachable database is /health's business.
    try:
        with Session(app.state.engine) as db_session:
            owner = ensure_owner(
                db_session,
                str(settings.owner_email),
                settings.owner_password.get_secret_value(),
            )
            db_session.commit()
        app_logging.logger.info(
            "owner account ensured", extra={"context": {"owner_id": str(owner.id)}}
        )
    except Exception as error:  # noqa: BLE001 - reported, not fatal when the DB is down
        app_logging.logger.warning(
            "owner account not ensured at startup: %s", type(error).__name__
        )

    # No job queue survives a restart: a build or render still `queued` or
    # `running` from a previous process is not running any more. Fail it here,
    # once, before any request can observe a job that looks alive but is not.
    try:
        swept = storage.sweep_orphaned_statuses(settings.render_root)
        if swept:
            app_logging.logger.info(
                "orphaned builds and renders failed at startup", extra={"context": {"count": swept}}
            )
    except Exception as error:  # noqa: BLE001 - reported, not fatal
        app_logging.logger.warning(
            "orphaned job sweep failed at startup: %s", type(error).__name__
        )

    # Per-agent model routing, validated against the registry (CLAUDE.md §4).
    # Developer-panel overrides in operator_settings resolve over the file.
    overrides = read_routing_overrides(app.state.engine)
    app.state.routing = load_routing(overrides=overrides)

    # Per-model generation profiles (defaults until the developer panel edits
    # them). Degrades to defaults if the store is unreadable.
    app.state.profiles = Profiles(app.state.engine)

    # The startup probe: one minimal call per distinct routed slug, so a blocked
    # model surfaces at boot as a configuration error rather than mid-session.
    # A guardrail block raises and stops startup.
    probe_ran = False
    if settings.gateway_probe_enabled:
        probe_models(settings, app.state.routing)
        probe_ran = True
    else:
        app_logging.logger.info("gateway probe skipped")

    # Tracing: off unless all three Langfuse values are set. Built once here so
    # a broken configuration is reported at startup rather than on a turn, and
    # so nothing is imported at all when it is not configured.
    app.state.tracing = Tracing(settings)

    # The benchmark is never measured at startup (it is the owner's explicit
    # request); the summary only says whether one is stored. An unreachable
    # database is /health's business.
    try:
        benchmark = "stored" if read_benchmark(app.state.engine) is not None else "missing"
    except Exception as error:  # noqa: BLE001 - reported, not fatal
        benchmark = f"unknown ({type(error).__name__})"

    app_logging.logger.info(
        "service ready",
        extra={
            "context": {
                "tracing": "on" if app.state.tracing.enabled else "off",
                "probe": "run" if probe_ran else "skipped",
                "routing": dict(app.state.routing.items()),
                "tiers": app.state.tiers.summary(),
                "benchmark": benchmark,
                **settings.safe_summary(),
            }
        },
    )

    try:
        yield
    finally:
        if app.state.checkpointer_pool is not None:
            app.state.checkpointer_pool.close()
        app.state.tracing.flush()
        app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    app_logging.configure_logging()
    settings = settings or get_settings()

    app = FastAPI(
        title="Home Renovation Agents",
        version="0.1.0",
        summary="Foundation — single-owner backend for custom-furniture design",
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    # At most one Blender process at a time, for the life of the app (render-guard
    # design decision 11). Built here, not in the lifespan, because `TestClient`
    # does not always run the lifespan and every route must find it.
    app.state.blender_semaphore = asyncio.Semaphore(1)
    # A test-only seam: `None` in production, always falling through to the real
    # `subprocess_launch`. Never read outside the render routes.
    app.state.blender_launch = None
    # The three render tiers (a bad render.yaml stops startup by name) and the
    # in-memory single-use approvals for `final` renders.
    app.state.tiers = load_tiers()
    app.state.render_approvals = ApprovalStore()
    app.state.auth_rate_limiter = RateLimiter(
        settings.auth_rate_limit, settings.auth_rate_limit_window_seconds
    )

    app.include_router(auth_router)
    app.include_router(health_router)
    app.include_router(packages_router)
    app.include_router(renders_router)
    app.include_router(admin_render_router)

    app_logging.install(app)
    # Added last so it sits outermost: preflight and error responses both need
    # the CORS headers, and credentials require explicit origins (never "*").
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app_logging.logger.info(
        "service starting", extra={"context": settings.safe_summary()}
    )
    return app
