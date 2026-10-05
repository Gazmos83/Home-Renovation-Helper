"""The rule-table derivation and the layer registry, without Blender."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.blender.custom_build import derive as rules
from app.blender.layers import LayerRegistrationError, LayerRegistry
from app.blender.schemas import CustomBuildSpec

TEMPLATES = Path(__file__).resolve().parents[1] / "fixtures/packages/templates"


@pytest.fixture
def desk() -> dict:
    document = json.loads((TEMPLATES / "fold-down-desk.json").read_text(encoding="utf-8"))
    return CustomBuildSpec.model_validate(document).model_dump(mode="json")


def test_the_desk_derives_parts_hardware_and_assembly(desk: dict) -> None:
    parts, hardware, assembly = rules.derive(desk)
    assert parts and hardware and assembly
    assert len({part["id"] for part in parts}) == len(parts), "cut-list ids are unique"


def test_the_emitted_spec_carries_what_the_studio_reads(desk: dict) -> None:
    emitted = rules.emitted_spec(desk)
    for key in ("overall", "modules", "parts", "hardware", "assembly", "layers"):
        assert key in emitted
    assert set(emitted["overall"]) == {"w", "h", "d"}
    assert set(emitted["modules"]) == {module["id"] for module in desk["modules"]}
    assert emitted["layers"] == {}, "the generator fills layers once meshes exist"


def test_the_layer_names_are_the_five_custom_build_layers() -> None:
    assert rules.LAYER_NAMES == ("carcass", "backs", "shelves", "fronts", "extras")
    assert set(LayerRegistry().groups) == set(rules.LAYER_NAMES)


def test_the_registry_records_each_mesh_once_in_one_layer() -> None:
    registry = LayerRegistry()
    registry.add("cabinet-side-l", "carcass")
    registry.add("cabinet-back", "backs")
    assert registry.as_json() == {"carcass": ["cabinet-side-l"], "backs": ["cabinet-back"]}
    assert registry.names == {"cabinet-side-l", "cabinet-back"}


def test_the_registry_refuses_a_duplicate_name() -> None:
    registry = LayerRegistry()
    registry.add("x", "carcass")
    with pytest.raises(LayerRegistrationError, match="duplicate"):
        registry.add("x", "backs")


def test_the_registry_refuses_an_unknown_layer() -> None:
    with pytest.raises(LayerRegistrationError, match="supported logical layer"):
        LayerRegistry().add("x", "steel")
