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
# Where Cycles computes: the laptop's CPU by default, a GPU back end on the render server.
CYCLES_DEVICES: Final = ("CPU", "OPTIX", "CUDA", "HIP")


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
    device: str = "CPU"
    # Show the piece's dimension lines (a piece's own turntable only, piece-inspector).
    dimensions: bool = False


def _after_separator(argv: list[str], flags: str) -> list[str]:
    if "--" not in argv:
        raise InputError(f"arguments: expected Blender separator '--' before {flags}")
    return argv[argv.index("--") + 1 :]


def _add_tier_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tier-frames", required=True, type=int)
    parser.add_argument("--tier-resolution", required=True, type=int)
    parser.add_argument("--tier-engine", required=True)
    parser.add_argument("--cycles-device", default="CPU")


def _tier_from(parsed: argparse.Namespace) -> TierArguments:
    if parsed.tier_frames < 1:
        raise InputError("arguments: --tier-frames must be at least 1")
    if parsed.tier_resolution < 1:
        raise InputError("arguments: --tier-resolution must be at least 1")
    if parsed.tier_engine not in RENDER_ENGINES:
        raise InputError(
            f"arguments: --tier-engine must be one of {', '.join(sorted(RENDER_ENGINES))}"
        )
    if parsed.cycles_device not in CYCLES_DEVICES:
        raise InputError(
            f"arguments: --cycles-device must be one of {', '.join(CYCLES_DEVICES)}"
        )
    return TierArguments(
        parsed.tier_frames,
        parsed.tier_resolution,
        parsed.tier_engine,
        parsed.cycles_device,
        getattr(parsed, "dimensions", False),
    )


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


def parse_build_arguments(argv: list[str]) -> tuple[Path, Path, Path | None]:
    """Resolved spec and output paths for the package build, and the version's frozen
    hardware inputs when the runner passes `--hardware-data` (none for an older version)."""
    parser = _ArgumentParser(add_help=False)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--hardware-data")
    parsed = parser.parse_args(_after_separator(argv, "--spec and --out"))
    hardware = _readable_file(parsed.hardware_data, "hardware data") if parsed.hardware_data else None
    return _readable_file(parsed.spec, "spec"), _new_output(parsed.out), hardware


def load_hardware_inputs(path: Path | None) -> dict | None:
    """The frozen hardware inputs a build derives with, or None when the version has none."""
    if path is None:
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InputError(f"hardware data: {path.name} is not readable JSON: {error}") from None
    if not isinstance(document, dict):
        raise InputError("hardware data: the file must hold one JSON object")
    return document


def parse_render_arguments(argv: list[str]) -> tuple[Path, Path, TierArguments]:
    """Resolved `model.blend` and output paths, and the tier, for a still or
    turntable of a built piece."""
    parser = _ArgumentParser(add_help=False)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dimensions", action="store_true")
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


def parse_composition_render_arguments(argv: list[str]) -> tuple[Path, Path, Path, Path, str, TierArguments]:
    """`render_composition.py`'s arguments: spec, pieces root, models root, out, kind and tier."""
    parser = argparse.ArgumentParser(prog="render_composition.py", add_help=False)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--pieces", required=True)
    parser.add_argument("--models", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--kind", required=True, choices=("still", "turntable"))
    _add_tier_arguments(parser)
    try:
        parsed = parser.parse_args(_after_separator(argv, "--spec"))
    except SystemExit:
        raise InputError("arguments: render_composition.py needs --spec, --pieces, --models, --out, --kind and the tier") from None
    return (
        _readable_file(parsed.spec, "--spec"), Path(parsed.pieces), Path(parsed.models), Path(parsed.out),
        parsed.kind, _tier_from(parsed),
    )


@dataclass(frozen=True, slots=True)
class RestyleArguments:
    """`render_restyle.py`'s arguments. A piece restyle names `blend`; a room restyle
    names `spec`, `pieces` and `models`. `restyle` is the validated look or style file."""

    restyle: Path
    out: Path
    tier: TierArguments
    blend: Path | None = None
    spec: Path | None = None
    pieces: Path | None = None
    models: Path | None = None


def parse_restyle_arguments(argv: list[str]) -> RestyleArguments:
    """Resolved paths and tier for one restyle still. Exactly one of `--blend` (a piece)
    or `--spec` with `--pieces` and `--models` (a composition) is required."""
    parser = _ArgumentParser(add_help=False)
    parser.add_argument("--restyle", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--blend")
    parser.add_argument("--spec")
    parser.add_argument("--pieces")
    parser.add_argument("--models")
    _add_tier_arguments(parser)
    parsed = parser.parse_args(_after_separator(argv, "--restyle, --out and the --tier-* values"))
    restyle = _readable_file(parsed.restyle, "restyle")
    out = _new_output(parsed.out)
    tier = _tier_from(parsed)
    if parsed.blend and not parsed.spec:
        return RestyleArguments(restyle, out, tier, blend=_readable_file(parsed.blend, "blend"))
    if parsed.spec and parsed.pieces and parsed.models and not parsed.blend:
        return RestyleArguments(
            restyle, out, tier, spec=_readable_file(parsed.spec, "spec"),
            pieces=Path(parsed.pieces), models=Path(parsed.models),
        )
    raise InputError("arguments: name --blend (a piece) or --spec, --pieces and --models (a composition)")
