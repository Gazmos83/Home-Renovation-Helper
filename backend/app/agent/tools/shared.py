"""Helpers the design tools share: reading versions, validating documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.agent import house_file
from app.agent.tools.base import (
    ToolContext,
    ToolDeps,
    extension_refusal,
    record_unknown_fields,
    unknown_fields,
)
from app.blender import storage
from app.blender.schemas import CustomBuildSpec, describe_validation_error
from app.blender.spec_contract import SpecValidationError
from app.packages import service

NOT_APPROVED = "this action needs the owner's confirmation first and was not run"


def conversation_piece(ctx: ToolContext) -> str | None:
    """The package id this conversation is bound to, or `None` while unbound."""
    if ctx.thread_id is None:
        return None
    with ctx.deps.session() as session:
        thread = house_file.get_thread(session, ctx.thread_id)
        return thread.package_id if thread is not None else None


def refuse_new_piece_when_bound(ctx: ToolContext) -> str | None:
    """A refusal when the conversation already has a piece, else `None`."""
    bound = conversation_piece(ctx)
    if bound is None:
        return None
    return (
        f"this conversation is about {bound}; create a new piece from the Pieces page "
        "with Create A New Piece"
    )


def refuse_other_piece(ctx: ToolContext, package_id: str) -> str | None:
    """A refusal when the conversation is bound to a different piece, else `None`."""
    bound = conversation_piece(ctx)
    if bound is None or bound == package_id:
        return None
    return (
        f"this conversation is about {bound}, not {package_id}; "
        f"open {package_id}'s conversation from the Pieces page"
    )


def builds_unavailable(deps: ToolDeps) -> str | None:
    """A refusal when no build can start on this host, else `None`."""
    if not deps.settings.generation_enabled:
        return "Blender is not available on this host, so nothing can be built or rendered"
    if deps.loop is None:
        return "the build queue is not running, so nothing can be built or rendered right now"
    return None


def checked_package_id(package_id: str) -> tuple[str | None, str]:
    try:
        return storage.validate_package_id(package_id), ""
    except storage.InvalidPackageId as error:
        return None, str(error)


def latest_version(deps: ToolDeps, package_id: str) -> int | None:
    found = storage.versions(deps.render_root, package_id)
    return found[-1] if found else None


def version_limit_refusal(deps: ToolDeps, package_id: str) -> str | None:
    """The code-written refusal when the piece already holds the most versions, else `None`."""
    if len(storage.versions(deps.render_root, package_id)) >= service.MAX_VERSIONS:
        return service.version_limit_message(package_id)
    return None


def version_limit_line(deps: ToolDeps, package_id: str) -> str | None:
    """The heads-up for a confirmation when the new version is one of the last three it can hold."""
    count = len(storage.versions(deps.render_root, package_id)) + 1
    if count > service.MAX_VERSIONS - 3:
        return f"This will be version {count} of {service.MAX_VERSIONS} the piece can hold."
    return None


def version_folder(deps: ToolDeps, package_id: str, version: int | None) -> tuple[Path | None, int | None, str]:
    """The folder of `version` (the latest when `None`), or a refusal."""
    package_id, problem = checked_package_id(package_id)
    if package_id is None:
        return None, None, problem
    number = version if version is not None else latest_version(deps, package_id)
    if number is None:
        return None, None, f"there is no package {package_id!r}"
    try:
        folder = storage.version_dir(deps.render_root, package_id, number)
    except ValueError:
        return None, None, f"version {number} is not a valid version"
    if not folder.is_dir():
        return None, None, f"package {package_id!r} has no version {number}"
    return folder, number, ""


def read_input(folder: Path) -> dict[str, Any] | None:
    try:
        return json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def validated_custom_build(
    ctx: ToolContext, document: Any, package_id: str | None
) -> tuple[dict[str, Any] | None, str]:
    """The normalised document, or a refusal.

    A field the schema does not define is refused by name and recorded as a
    generator-extension request with the owner's last message (ladder step 2).
    """
    try:
        return CustomBuildSpec.model_validate(document).model_dump(mode="json"), ""
    except ValidationError as error:
        message = describe_validation_error(error)
        fields = unknown_fields(error)
        if fields:
            record_unknown_fields(ctx, fields, package_id)
            return None, extension_refusal(message, fields)
        return None, message
    except SpecValidationError as error:
        return None, str(error)
