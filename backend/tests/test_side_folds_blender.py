"""carcass-side-folds: the 26° left height-fold fixture, built in the pinned Blender (--blender)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.blender.schemas import CustomBuildSpec
from tests.test_custom_build_generator import _build, _inspect
from tests.test_side_folds import folded_cabinet

pytestmark = pytest.mark.blender


@pytest.fixture(scope="module")
def built(blender_bin: Path, tmp_path_factory: pytest.TempPathFactory):
    tmp = tmp_path_factory.mktemp("side-folds")
    spec = CustomBuildSpec.model_validate(folded_cabinet()).model_dump(mode="json")
    result, out = _build(blender_bin, spec, tmp)
    assert result.returncode == 0, result.stderr[-800:]
    return spec, out


def test_the_lower_and_upper_left_sides_meet_at_1100_mm(built, blender_bin: Path) -> None:
    _spec, out = built
    objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    lower = objects["cabinet-side-left-lower"]
    upper = objects["cabinet-side-left-upper"]
    right = objects["cabinet-side-right"]
    lower_z = [corner[2] for corner in lower["bound_box"]]
    upper_z = [corner[2] for corner in upper["bound_box"]]
    assert max(lower_z) == pytest.approx(1.100, abs=0.0001)
    assert min(abs(z - 1.100) for z in upper_z) == pytest.approx(0, abs=0.0001)
    join_lower = [c for c in lower["bound_box"] if abs(c[2] - 1.100) < 0.0001]
    join_upper = [c for c in upper["bound_box"] if abs(c[2] - 1.100) < 0.0001]
    distance = min(
        ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5
        for a in join_lower
        for b in join_upper
    )
    assert distance == pytest.approx(0, abs=0.0001)
    assert abs(upper["rotation_deg"][1]) == pytest.approx(26, abs=0.1)
    right_z = [corner[2] for corner in right["bound_box"]]
    assert min(right_z) == pytest.approx(0, abs=0.0001)
    assert max(right_z) == pytest.approx(2.000, abs=0.0001)
    assert right["rotation_deg"] == pytest.approx([0, 0, 0], abs=0.1)


def test_the_layers_list_the_folded_carcass_and_back(built) -> None:
    _spec, out = built
    emitted = json.loads((out / "spec.json").read_text(encoding="utf-8"))
    carcass = set(emitted["layers"]["carcass"])
    assert {"cabinet-side-left-lower", "cabinet-side-left-upper", "cabinet-side-right"} <= carcass
    assert "cabinet-back" in emitted["layers"]["backs"]


@pytest.fixture(scope="module")
def built_doors(blender_bin: Path, tmp_path_factory: pytest.TempPathFactory):
    tmp = tmp_path_factory.mktemp("side-folds-doors")
    spec = CustomBuildSpec.model_validate(
        folded_cabinet(shelves=4, fronts=[{"type": "door", "count": 2, "opening": "hinge"}])
    ).model_dump(mode="json")
    result, out = _build(blender_bin, spec, tmp)
    assert result.returncode == 0, result.stderr[-800:]
    return spec, out


def test_two_doors_on_the_26_degree_cabinet_are_drawn_in_the_fronts_layer(
    built_doors, blender_bin: Path
) -> None:
    _spec, out = built_doors
    emitted = json.loads((out / "spec.json").read_text(encoding="utf-8"))
    fronts = set(emitted["layers"]["fronts"])
    assert {"cabinet-door-1-1", "cabinet-door-1-2"} <= fronts
    objects = {o["name"]: o for o in _inspect(blender_bin, out / "model.blend")["objects"]}
    left = objects["cabinet-door-1-1"]
    right = objects["cabinet-door-1-2"]
    right_z = [corner[2] for corner in right["bound_box"]]
    assert min(right_z) == pytest.approx(0.0015, abs=0.0002)
    assert max(right_z) == pytest.approx(1.9985, abs=0.0002)
    assert right["rotation_deg"] == pytest.approx([0, 0, 0], abs=0.1)
    left_z = [corner[2] for corner in left["bound_box"]]
    assert max(left_z) < max(right_z) - 0.05
    xs_at_kink = [v[0] for v in left["vertices"] if abs(v[2] - 1.100) < 0.002]
    xs_near_top = [v[0] for v in left["vertices"] if v[2] > 1.5]
    assert xs_at_kink
    assert xs_near_top
    assert min(xs_near_top) > min(xs_at_kink)
