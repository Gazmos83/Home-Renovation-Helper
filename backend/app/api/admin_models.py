"""Developer panel: registry, routing, generation profiles and token restrictions."""

from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.agent.models.budgets import InvalidBudgetSettings
from app.agent.models.probe import probe_slug
from app.agent.models.profiles import InvalidGenerationSettings
from app.agent.models.registry import BY_ID, MODELS, is_available, is_known
from app.agent.models.routing import (
    IMAGE_SLOTS,
    SLOTS,
    delete_routing_override,
    load_routing,
    read_routing_overrides,
    write_routing_override,
)
from app.agent.models.slots import LOOP_SLOTS, build_slot_models
from app.api.gate import require_dev
from app.config import ConfigurationError
from app.observability.usage import tokens_today

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_dev)])


class RoutingIn(BaseModel):
    model: str


class GenerationIn(BaseModel):
    temperature: float | None = None
    max_output_tokens: int | None = None


class BudgetIn(BaseModel):
    context_budget_tokens: int = Field(ge=1)
    daily_token_ceiling: int = Field(ge=1)


def _refused(code: int, failure_class: str, reason: str, field: str | None = None) -> HTTPException:
    detail: dict[str, Any] = {"failure_class": failure_class, "reason": reason}
    if field:
        detail["field"] = field
    return HTTPException(code, detail=detail)


def _swap_lock(request: Request) -> threading.Lock:
    lock = getattr(request.app.state, "swap_lock", None)
    if lock is None:
        lock = threading.Lock()
        request.app.state.swap_lock = lock
    return lock


def _rebuild_models(request: Request) -> None:
    app = request.app
    app.state.models = build_slot_models(app.state.settings, app.state.routing, app.state.profiles)


def _reload_routing(request: Request) -> None:
    overrides = read_routing_overrides(request.app.state.engine)
    request.app.state.routing = load_routing(overrides=overrides)


@router.get("/models")
def list_models(request: Request) -> dict[str, Any]:
    overrides = read_routing_overrides(request.app.state.engine)
    routing = request.app.state.routing
    profiles = request.app.state.profiles
    budgets = request.app.state.budgets
    tz = request.app.state.settings.budget_timezone
    registry = [
        {
            "slug": entry.model_id,
            "display_name": entry.display_name,
            "context_window": entry.context_window,
            "supports_temperature": entry.supports_temperature,
            "supports_images": entry.supports_images,
            "available": entry.availability == "available",
        }
        for entry in MODELS
    ]
    slots = [
        {
            "slot": slot,
            "model": routing.model_for(slot),
            "override": slot in overrides,
        }
        for slot in SLOTS
    ]
    models = []
    for entry in MODELS:
        if entry.availability != "available":
            continue
        profile = profiles.profile_for(entry.model_id)
        restrictions = budgets.for_model(entry.model_id)
        models.append(
            {
                "slug": entry.model_id,
                "temperature": profile.temperature,
                "max_output_tokens": profile.max_output_tokens,
                "context_budget_tokens": restrictions.context_budget_tokens,
                "daily_token_ceiling": restrictions.daily_token_ceiling,
                "usage_today": tokens_today(
                    request.app.state.engine, entry.model_id, tz
                ),
            }
        )
    return {"registry": registry, "slots": slots, "models": models}


@router.put("/routing/{slot}")
def set_routing(slot: str, body: RoutingIn, request: Request) -> dict[str, Any]:
    if slot not in SLOTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    slug = body.model
    if not is_known(slug) or not is_available(slug):
        raise _refused(422, "unknown_model", f"unknown or unavailable model {slug}", "model")
    try:
        probe_slug(request.app.state.settings, slug, image=slot in IMAGE_SLOTS)
    except ConfigurationError as error:
        raise _refused(422, "probe_failed", str(error), "model") from None
    with _swap_lock(request):
        write_routing_override(request.app.state.engine, slot, slug)
        _reload_routing(request)
        if slot in LOOP_SLOTS:
            _rebuild_models(request)
    return {"slot": slot, "model": slug, "override": True}


@router.delete("/routing/{slot}")
def reset_routing(slot: str, request: Request) -> dict[str, Any]:
    if slot not in SLOTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    with _swap_lock(request):
        delete_routing_override(request.app.state.engine, slot)
        _reload_routing(request)
        if slot in LOOP_SLOTS:
            _rebuild_models(request)
    return {"slot": slot, "model": request.app.state.routing.model_for(slot), "override": False}


@router.put("/models/{slug:path}/generation")
def set_generation(slug: str, body: GenerationIn, request: Request) -> dict[str, Any]:
    if slug not in BY_ID:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    try:
        profile = request.app.state.profiles.set_generation(
            slug,
            temperature=body.temperature,
            max_output_tokens=body.max_output_tokens,
            actor="owner",
        )
    except InvalidGenerationSettings as error:
        field = "temperature" if "temperature" in str(error) else "max_output_tokens"
        raise _refused(422, "invalid_generation", str(error), field) from None
    with _swap_lock(request):
        _rebuild_models(request)
    return {
        "slug": slug,
        "temperature": profile.temperature,
        "max_output_tokens": profile.max_output_tokens,
    }


@router.delete("/models/{slug:path}/generation")
def reset_generation(slug: str, request: Request) -> dict[str, Any]:
    if slug not in BY_ID:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    request.app.state.profiles.reset_generation(slug)
    with _swap_lock(request):
        _rebuild_models(request)
    return {"slug": slug, "temperature": None, "max_output_tokens": None}


@router.put("/models/{slug:path}/budget")
def set_budget(slug: str, body: BudgetIn, request: Request) -> dict[str, Any]:
    if slug not in BY_ID:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    try:
        restrictions = request.app.state.budgets.set_budget(
            slug,
            context_budget_tokens=body.context_budget_tokens,
            daily_token_ceiling=body.daily_token_ceiling,
        )
    except InvalidBudgetSettings as error:
        field = "context_budget_tokens" if "context_budget" in str(error) else "daily_token_ceiling"
        raise _refused(422, "invalid_budget", str(error), field) from None
    return {
        "slug": slug,
        "context_budget_tokens": restrictions.context_budget_tokens,
        "daily_token_ceiling": restrictions.daily_token_ceiling,
    }


@router.delete("/models/{slug:path}/budget")
def reset_budget(slug: str, request: Request) -> dict[str, Any]:
    if slug not in BY_ID:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    request.app.state.budgets.reset_budget(slug)
    restrictions = request.app.state.budgets.for_model(slug)
    return {
        "slug": slug,
        "context_budget_tokens": restrictions.context_budget_tokens,
        "daily_token_ceiling": restrictions.daily_token_ceiling,
    }
