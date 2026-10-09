"""shelf-spacing-and-dividers: a divided module with stated shelf spacing, built in the pinned Blender (--blender)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.blender.custom_build import derive as rules
from app.blender.schemas import CustomBuildSpec
from tests.test_custom_build_generator import _build, _inspect

pytestmark = pytest.mark.blender

SPEC = {
    "kind": "custom_build", "schema_version": 1, "units": "mm", "name": "Divided shelf",
    "materials": {"carcass": {"material": "Spanplatte 18 mm", "thickness_mm": 18}},
    "modules": [
        {
            "id": "cabinet", "name": "Cabinet", "x": 0, "y": 0, "z": 0, "width": 1000, "height": 1600,
            "depth": 400, "carcass": "carcass", "shelves": 4, "shelf_spacing_mm": 355, "dividers": 2,
        }
    ],
}


@pytest.fixture(scope="module")
def built(blender_bin: Path, tmp_path_factory: pytest.TempPathFactory):
    tmp = tmp_path_factory.mktemp("divided")
    spec = CustomBuildSpec.model_validate(SPEC).model_dump(mode="json")
    result, out = _build(blender_bin, spec, tmp)
    assert result.returncode == 0, result.stderr
    return spec, out


def test_dividers_and_shelves_are_objects_at_their_heights(built, blender_bin: Path) -> None:
    spec, out = built
    objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    dividers = [name for name in objects if name.split("#")[0] == "cabinet-divider"]
    shelves = [name for name in objects if name.split("#")[0] == "cabinet-shelf"]
    assert len(dividers) == 2 and len(shelves) == 12
    # world z of each board's centre, in metres: bottom panel top (18) + underside + half a board
    heights = sorted({round(objects[name]["location"][2] * 1000, 1) for name in shelves})
    assert heights == pytest.approx([18 + u + 9 for u in rules.shelf_undersides(spec["modules"][0], 18)], abs=0.1)
    assert heights == pytest.approx([382, 755, 1128, 1501], abs=0.1)


def test_the_layers_list_the_dividers_and_shelves(built) -> None:
    _spec, out = built
    emitted = json.loads((out / "spec.json").read_text(encoding="utf-8"))
    assert {"cabinet-divider", "cabinet-divider#2"} <= set(emitted["layers"]["carcass"])
    assert len([name for name in emitted["layers"]["shelves"] if name.startswith("cabinet-shelf")]) == 12
