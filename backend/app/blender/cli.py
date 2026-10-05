"""Portable command/input helpers that can be tested without Blender.

Standard library only (plus the dependency-free contracts): a background `bpy`
process imports this module, and Blender's Python has no Pydantic or PyYAML.

The three generators take their tier values as `--tier-*` arguments. Only the
runner writes them, from a ticket the render guard issued; nothing a caller or a
model supplies reaches argv (render-guard design decision 6).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.blender.custom_build.derive import DeriveError, derive

# Blender 5.2.1 RNA identifiers a tier may use (see app.render.tiers.ENGINES).
RENDER_ENGINES: Final = frozenset({"BLENDER_EEVEE", "CYCLES"})


class InputError(RuntimeError):
    """A concise command or input failure safe to show to an operator."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputError(f"arguments: {message}")


@dataclass(frozen=True, slots=True)
class TierArguments:
    frames: int
    resolution: int
    engine: str


def _after_separator(argv: list[str], flags: str) -> list[str]:
    if "--" not in argv:
        raise InputError(f"arguments: expected Blender separator '--' before {flags}")
    return argv[argv.index("--") + 1 :]


def _add_tier_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tier-frames", required=True, type=int)
    parser.add_argument("--tier-resolution", required=True, type=int)
    parser.add_argument("--tier-engine", required=True)


def _tier_from(parsed: argparse.Namespace) -> TierArguments:
    if parsed.tier_frames < 1:
        raise InputError("arguments: --tier-frames must be at least 1")
    if parsed.tier_resolution < 1:
        raise InputError("arguments: --tier-resolution must be at least 1")
    if parsed.tier_engine not in RENDER_ENGINES:
        raise InputError(
            f"arguments: --tier-engine must be one of {', '.join(sorted(RENDER_ENGINES))}"
        )
    return TierArguments(parsed.tier_frames, parsed.tier_resolution, parsed.tier_engine)


def _readable_file(value: str, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise InputError(f"arguments: {label} is not a readable file: {path}")
    return path


def _new_output(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if path.exists():
        raise InputError(f"arguments: output path already exists: {path}")
    if not path.parent.is_dir():
        raise InputError(f"arguments: output parent does not exist: {path.parent}")
    return path


def parse_generator_arguments(argv: list[str]) -> tuple[Path, Path]:
    """Resolved spec and output paths for the package build."""
    parser = _ArgumentParser(add_help=False)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    parsed = parser.parse_args(_after_separator(argv, "--spec and --out"))
    return _readable_file(parsed.spec, "spec"), _new_output(parsed.out)


def parse_render_arguments(argv: list[str]) -> tuple[Path, Path, TierArguments]:
    """Resolved `model.blend` and output paths, and the tier, for a still or
    turntable of a built piece."""
    parser = _ArgumentParser(add_help=False)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out", required=True)
    _add_tier_arguments(parser)
    parsed = parser.parse_args(_after_separator(argv, "--blend, --out and the --tier-* values"))
    return _readable_file(parsed.blend, "blend"), _new_output(parsed.out), _tier_from(parsed)


def parse_room_generator_arguments(
    argv: list[str],
) -> tuple[Path, Path, Path, TierArguments]:
    """Resolved scene document, package directory, output path and tier for a
    room render.

    The package directory must already hold `model.glb` and `spec.json`, checked
    before any Blender work starts.
    """
    parser = _ArgumentParser(add_help=False)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--out", required=True)
    _add_tier_arguments(parser)
    parsed = parser.parse_args(
        _after_separator(argv, "--scene, --package, --out and the --tier-* values")
    )

    scene_path = _readable_file(parsed.scene, "scene")
    package_dir = Path(parsed.package).expanduser().resolve()
    if not package_dir.is_dir():
        raise InputError(f"arguments: package directory does not exist: {package_dir}")
    for name in ("model.glb", "spec.json"):
        if not (package_dir / name).is_file():
            raise InputError(f"arguments: package directory is missing {name}: {package_dir}")
    return scene_path, package_dir, _new_output(parsed.out), _tier_from(parsed)


def load_json(path: Path) -> dict:
    """Load and parse a JSON document with a concise diagnostic on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        raise InputError(f"validation: input is not UTF-8 JSON: {path}") from error
    except json.JSONDecodeError as error:
        raise InputError(f"validation: malformed JSON in {path}: line {error.lineno}") from error


def load_custom_build(path: Path) -> dict:
    """Load a stored, already-normalised custom-build specification.

    The backend validated it with `CustomBuildSpec` before storing it; Blender's
    Python has no Pydantic, so this checks only the document's identity and that
    the shared rule table can derive it.
    """
    document = load_json(path)
    if not isinstance(document, dict) or document.get("kind") != "custom_build":
        raise InputError("validation: kind must be 'custom_build'")
    if document.get("schema_version") != 1:
        raise InputError("validation: schema_version must be 1")
    if document.get("units") != "mm":
        raise InputError("validation: units must be 'mm'")
    try:
        derive(document)
    except (DeriveError, KeyError, TypeError) as error:
        raise InputError(f"validation: {error}") from error
    return document


def load_shell(path: Path) -> dict:
    """Load a stored apartment-shell document and validate it with the shared contract."""
    from app.blender.shell_contract import SpecValidationError, normalise_shell

    document = load_json(path)
    try:
        normalise_shell(document)
    except SpecValidationError as error:
        raise InputError(f"validation: {error}") from error
    return document
