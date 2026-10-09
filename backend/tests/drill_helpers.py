"""Builders for the hardware-drilling tests: a normalised spec and the frozen inputs it is derived with."""

from __future__ import annotations

from typing import Any

from app.blender.schemas import CustomBuildSpec

SOURCE = "maker data sheet p. 4"
BRACKET_SOURCE = {"publication": "topnotch-shelf-brackets", "section": "Where Should Shelf Brackets Be Positioned?", "quote": "q"}
COUNT_TABLE = [
    {"max_length_mm": 600, "min_brackets": 2}, {"max_length_mm": 1200, "min_brackets": 2},
    {"max_length_mm": 1800, "min_brackets": 3}, {"max_length_mm": 2000, "min_brackets": 4},
]


def exact(value: float) -> dict[str, float]:
    return {"value": value}


def ranged(low: float, high: float) -> dict[str, float]:
    return {"min": low, "max": high}


def sheet(kind: str, values: dict[str, Any], *, maker: str = "Maker", model: str = "M1") -> dict[str, Any]:
    return {
        "kind": kind, "maker": maker, "model": model, "values": values, "source": SOURCE,
        "updated_at": "2026-10-08T00:00:00+00:00",
    }


def rules(*, count: bool = True, end: dict[str, float] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if count:
        out["shelf_bracket_count_for_length"] = {
            "rule_id": "bracket-count", "params": {"table": COUNT_TABLE}, "source": BRACKET_SOURCE,
        }
    if end is not None:
        out["shelf_bracket_spacing_mm"] = {
            "rule_id": "bracket-spacing", "params": {"end_distance_mm": end, "even_tolerance_mm": 10},
            "source": BRACKET_SOURCE,
        }
    return out


def inputs(sheets: dict[str, dict[str, Any]] | None = None, rule_set: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data_sheets": sheets or {}, "rules": rule_set or {}}


def build(*, modules: list[dict[str, Any]] | None = None, wall_shelves: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    document = {
        "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Test build",
        "materials": {
            "carcass": {"material": "Spanplatte 18 mm", "thickness_mm": 18},
            "back": {"material": "HDF 3 mm", "thickness_mm": 3},
            "oak": {"material": "Eiche 18 mm", "thickness_mm": 18},
        },
        "envelope": {"width": 3000, "height": 2400, "depth": 600},
        "modules": modules or [],
        "wall_shelves": wall_shelves or [],
    }
    return CustomBuildSpec.model_validate(document).model_dump(mode="json")


def module(**fields: Any) -> dict[str, Any]:
    base = {
        "id": "m", "name": "Cabinet", "x": 0, "y": 0, "z": 0, "width": 600, "height": 720, "depth": 400,
        "carcass": "carcass", "back": "back",
    }
    return base | fields


def wall_shelf(**fields: Any) -> dict[str, Any]:
    base = {
        "id": "wall-shelf-1", "name": "Wall shelf", "x": 100, "z": 1400, "length": 1200, "depth": 250,
        "material": "oak", "bracket": "bracket-white",
    }
    return base | fields
