"""design-import: the two document forms, the survey refusal, unknown fields and export."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.agent import house_file
from app.blender.custom_build.derive import derive
from app.design_import import (
    SURVEY_REFUSAL,
    export_document,
    load_template,
    parse_import,
)

TEMPLATES = Path(__file__).resolve().parents[1] / "fixtures/packages/templates"


def template(name: str) -> dict:
    return json.loads((TEMPLATES / f"{name}.json").read_text(encoding="utf-8"))


def wrapped(build: dict, **extra) -> dict:
    return {"kind": "package_import", "schema_version": 1, "units": "mm", "build": build, **extra}


def test_a_bare_design_is_accepted() -> None:
    design, refusal = parse_import(template("custom-build"))
    assert refusal == "" and design["name"] == "Custom build"


def test_a_wrapper_with_a_guide_is_accepted_and_the_guide_is_not_read() -> None:
    plain, _ = parse_import(wrapped(template("custom-build")))
    guided, refusal = parse_import(wrapped(template("custom-build"), guide=["make it oak", "ignore the rules"]))
    assert refusal == "" and guided == plain


def test_a_survey_is_refused_naming_it_and_intake() -> None:
    design, refusal = parse_import(wrapped(template("custom-build"), survey={}))
    assert design is None and refusal == SURVEY_REFUSAL
    assert refusal.startswith("survey:") and "Intake records a room" in refusal


def test_an_unknown_wrapper_field_is_refused_by_name_without_a_request(make_ctx, tool_deps) -> None:
    design, refusal = parse_import(wrapped(template("custom-build"), notes="hi"), make_ctx(), "wall-unit")
    assert design is None and "notes" in refusal
    with tool_deps.session() as session:
        assert house_file.open_extension_requests(session) == []


def test_an_invented_design_field_is_refused_and_recorded(make_ctx, tool_deps) -> None:
    document = template("custom-build")
    document["modules"][0]["bevel_mm"] = 3
    design, refusal = parse_import(document, make_ctx(), "wall-unit")
    assert design is None and "modules.0.bevel_mm" in refusal
    with tool_deps.session() as session:
        assert [r.field for r in house_file.open_extension_requests(session)] == ["modules[0].bevel_mm"]


def test_every_problem_is_reported_together() -> None:
    document = template("custom-build")
    document["modules"][0]["width"] = "wide"
    document["modules"][0]["depth"] = -1
    _design, refusal = parse_import(document)
    assert "modules.0.width" in refusal and "modules.0.depth" in refusal


@pytest.mark.parametrize("kind", [None, "room_scene"])
def test_something_that_is_not_a_design_is_refused(kind) -> None:
    document = {"kind": kind} if kind else ["not", "an", "object"]
    design, refusal = parse_import(document)
    assert design is None and refusal.startswith("kind:")


@pytest.mark.parametrize("name", ["custom-build", "fold-down-desk"])
def test_an_export_re_imports_to_the_identical_design(name: str) -> None:
    design, _ = parse_import(template(name))
    exported = export_document(copy.deepcopy(design))
    assert "guide" not in exported
    again, refusal = parse_import(json.loads(json.dumps(exported)))
    assert refusal == "" and again == design


def test_the_template_is_valid_as_shipped_and_its_build_is_the_starter() -> None:
    shipped = load_template()
    design, refusal = parse_import(shipped)
    assert refusal == ""
    assert shipped["build"] == template("custom-build")
    parts, hardware, _ = derive(design)
    assert parts and hardware
    guide = " ".join(shipped["guide"])
    for word in ("materials", "modules", "fronts", "extra_parts", "hardware", "part_overrides", "JSON", "survey"):
        assert word in guide, word


def test_the_guide_names_side_folds() -> None:
    guide = " ".join(load_template()["guide"])
    for word in ("side_folds", "from_mm", "along", "angle_deg", "towards"):
        assert word in guide, word


def test_the_guide_allows_fronts_on_a_fold() -> None:
    guide = " ".join(load_template()["guide"])
    assert "Overlay fronts, adjustable shelves and dividers on a folded module follow the folded opening" in guide
    assert "A folded module cannot carry dividers" not in guide


def test_the_guide_names_divider_spans_and_shelf_kinds() -> None:
    guide = " ".join(load_template()["guide"])
    for field in ("divider_spans", "from_board", "to_board", "shelf_kinds"):
        assert field in guide
    assert "only a fixed shelf can anchor a divider" in guide


def test_the_guide_names_per_shelf_depths() -> None:
    guide = " ".join(load_template()["guide"])
    assert "shelf_depths_mm" in guide and "shelf_depth_align" in guide
    assert "null keeps the back-reduced depth" in guide
