"""`blender_build` (Builder): build a version and report the screenshot.

Builds wait: the tool runs the build on the app's event loop and waits within
the Blender timeout, so the Builder can name the screenshot in the same reply.
A build already started (by `create_piece`) is waited for; one already
succeeded is reported as built without rebuilding.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from pydantic import BaseModel, Field

from app.agent import house_file, notices
from app.agent.tools.base import AgentTool, ToolContext, parse_args
from app.agent.tools.shared import builds_unavailable, version_folder
from app.blender import runner, storage
from app.packages import service

POLL_SECONDS = 0.25
GRACE_SECONDS = 30.0


class BuildArgs(BaseModel):
    package_id: str
    version: int | None = Field(default=None, description="a version number; the latest when left out")


def screenshot_route(package_id: str, version: int) -> str:
    return f"/packages/{package_id}/versions/{version}/files/screenshot.png"


def _wait_for_running(ctx: ToolContext, folder, limit: float) -> dict[str, Any]:
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        state = storage.read_status(folder) or {}
        if state.get("status") in ("succeeded", "failed"):
            return state
        time.sleep(POLL_SECONDS)
    return storage.read_status(folder) or {}


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(BuildArgs, arguments)
    if args is None:
        return problem
    folder, number, problem = version_folder(ctx.deps, args.package_id, args.version)
    if folder is None or number is None:
        return problem
    package_id = args.package_id
    where = f"{package_id} version {number}"
    state = storage.read_status(folder) or {}

    if state.get("status") == "succeeded":
        return (
            f"{where} is already built; nothing was rebuilt. "
            f"Screenshot: {screenshot_route(package_id, number)}"
        )
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable

    limit = ctx.deps.settings.blender_timeout_seconds + GRACE_SECONDS
    if state.get("status") in ("queued", "running"):
        # Started already (by `create_piece`); wait for it rather than start a second.
        state = _wait_for_running(ctx, folder, limit)
    else:
        runner.mark_build_queued(folder)
        future = ctx.deps.start_build(package_id, number)
        notices.follow_build(ctx.deps, ctx.thread_id, future, package_id, number)
        try:
            future.result(timeout=limit)
        except FutureTimeout:
            future.cancel()
            return f"{where} did not finish building within the time limit; it may still be running"
        state = storage.read_status(folder) or {}

    if state.get("status") == "succeeded":
        return f"Built {where}. Screenshot: {screenshot_route(package_id, number)}"
    if state.get("status") == "failed":
        return f"The build of {where} failed: {state.get('error') or 'no reason was recorded'}"
    return f"{where} is still building; ask again in a moment"


blender_build = AgentTool(
    name="blender_build",
    description=(
        "Build a piece's version into a 3D model and wait for it. Reports the screenshot route. "
        "A version that is already built is reported, not rebuilt."
    ),
    schema=BuildArgs,
    run=run,
)


class BuildShellArgs(BaseModel):
    apartment_name: str = Field(description="the apartment's name, as in the house file")


def shell_screenshot_route(slug: str, version: int) -> str:
    return f"/apartments/{slug}/shell/versions/{version}/files/screenshot.png"


def run_shell(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(BuildShellArgs, arguments)
    if args is None:
        return problem
    with ctx.deps.session() as session:
        apartment = house_file.find_apartment(session, args.apartment_name)
        if apartment is None:
            known = ", ".join(a.name for a in house_file.apartments(session)) or "none"
            return f"there is no apartment {args.apartment_name!r} in the house file; its apartments are: {known}"
        try:
            document = house_file.apartment_shell_document(session, apartment)
        except house_file.HouseFileError as error:
            return f"the apartment cannot be built: {error}"
        slug = storage.apartment_slug(apartment.name)

    root = ctx.deps.render_root
    existing = storage.shell_versions(root, slug)
    if existing:
        latest = storage.shell_version_dir(root, slug, existing[-1])
        try:
            same = json.loads((latest / storage.INPUT_FILE).read_text(encoding="utf-8")) == document
        except (OSError, ValueError):
            same = False
        if same and (storage.read_status(latest) or {}).get("status") == "succeeded":
            return (
                f"{apartment.name} version {existing[-1]} is already built from these rooms; nothing was "
                f"rebuilt. Screenshot: {shell_screenshot_route(slug, existing[-1])}"
            )
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable

    holder: dict[str, Any] = {}

    def start(version: int) -> None:
        holder["future"] = ctx.deps.start_build(slug, version, "shell")

    created = service.create_shell_version(root, slug, document, start)
    version = created["version"]
    where = f"{apartment.name} shell version {version}"
    try:
        holder["future"].result(timeout=ctx.deps.settings.blender_timeout_seconds + 30)
    except FutureTimeout:
        holder["future"].cancel()
        return f"{where} did not finish building within the time limit; it may still be running"
    state = storage.read_status(storage.shell_version_dir(root, slug, version)) or {}
    if state.get("status") == "succeeded":
        return f"Built {where}. Screenshot: {shell_screenshot_route(slug, version)}"
    if state.get("status") == "failed":
        return f"The build of {where} failed: {state.get('error') or 'no reason was recorded'}"
    return f"{where} is still building; ask again in a moment"


build_shell = AgentTool(
    name="build_shell",
    description=(
        "Build an apartment's shell (floors, walls, openings) from the rooms in the house file and "
        "wait for it. Reports the screenshot route. A shell whose rooms are unchanged is reported, "
        "not rebuilt."
    ),
    schema=BuildShellArgs,
    run=run_shell,
)
