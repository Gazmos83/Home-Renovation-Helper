"""Creating a package version, shared by the package routes and the agent tools.

A version is a folder under the render root holding its input document; the
build is started by the caller (a background task in a route, the app's event
loop for an agent tool) through `start`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.blender import runner, storage

logger = logging.getLogger("app")


def create_version(
    root: Path,
    package_id: str,
    spec: dict[str, Any],
    start: Callable[[int], None],
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write the next version's input (and its frozen hardware inputs), mark it queued, hand it to `start`."""
    version = storage.next_version(root, package_id)
    folder = storage.version_dir(root, package_id, version)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(json.dumps(spec, indent=2), encoding="utf-8")
    if inputs is not None:
        storage.write_hardware_inputs(folder, inputs)
    runner.mark_build_queued(folder)
    start(version)
    logger.info(
        "package version created",
        extra={"context": {"package_id": package_id, "version": version}},
    )
    return {"package_id": package_id, "version": version, "status": "queued"}


class RoomDocumentRefused(ValueError):
    """A room-scene document the render cannot use; the message names why."""


def room_scene_document(folder: Path, kind: str, room: Any) -> dict[str, Any]:
    """The normalised room-scene document for a render of `kind` of this version.

    The document's own `output.kind` is set to the render's kind: the kind is
    the request's, and the tier decides everything else.
    """
    from pydantic import ValidationError

    from app.blender.room_contract import normalise_room_scene
    from app.blender.schemas import RoomSceneSpec, describe_validation_error
    from app.blender.spec_contract import SpecValidationError

    if not isinstance(room, dict):
        raise RoomDocumentRefused("room must be a room-scene document")
    document = {**room, "output": {"kind": kind}}
    try:
        spec = RoomSceneSpec.model_validate(document)
    except ValidationError as error:
        raise RoomDocumentRefused(describe_validation_error(error)) from None
    try:
        overall = json.loads((folder / "spec.json").read_text(encoding="utf-8"))["overall"]
        normalise_room_scene(spec.model_dump(mode="json"), package_overall={k: float(v) for k, v in overall.items()})
    except SpecValidationError as error:
        raise RoomDocumentRefused(str(error)) from None
    except (OSError, KeyError, ValueError, TypeError):
        raise RoomDocumentRefused(
            "this version has no readable spec.json to place in a room; build it first"
        ) from None
    return spec.model_dump(mode="json")


def create_shell_version(
    root: Path,
    slug: str,
    document: dict[str, Any],
    start: Callable[[int], None],
) -> dict[str, Any]:
    """Write the next shell version's input, mark it queued and hand it to `start`."""
    version = storage.next_shell_version(root, slug)
    folder = storage.shell_version_dir(root, slug, version)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(json.dumps(document, indent=2), encoding="utf-8")
    runner.mark_build_queued(folder)
    start(version)
    logger.info(
        "shell version created", extra={"context": {"apartment": slug, "version": version}}
    )
    return {"apartment": slug, "version": version, "status": "queued"}
