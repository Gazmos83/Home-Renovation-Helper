"""room-composition: a composition build's files and its surface map (app-check-2026-10-09)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.blender.verify import VerificationError, glb_mesh_nodes, verify_composition
from tests.blender_fakes import glb_bytes, write_composition_files


def test_the_glbs_mesh_nodes_are_read_from_its_json_chunk(tmp_path: Path) -> None:
    (tmp_path / "model.glb").write_bytes(glb_bytes(["Floor", "Wall_0_0"]))
    assert glb_mesh_nodes(tmp_path / "model.glb") == ["Floor", "Wall_0_0"]


def test_a_composition_whose_map_covers_every_mesh_once_passes(tmp_path: Path) -> None:
    write_composition_files(tmp_path / "out")
    verify_composition(tmp_path / "out")


def _with_surfaces(out: Path, surfaces: dict) -> None:
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    (out / "report.json").write_text(json.dumps({**report, "surfaces": surfaces}), encoding="utf-8")


def test_an_unmapped_mesh_fails(tmp_path: Path) -> None:
    out = tmp_path / "out"
    write_composition_files(out)
    _with_surfaces(out, {"floor": ["Floor"], "ceiling": ["Ceiling"]})
    with pytest.raises(VerificationError, match="unmapped \\['Wall_0_0'\\]"):
        verify_composition(out)


def test_a_mesh_mapped_twice_fails(tmp_path: Path) -> None:
    out = tmp_path / "out"
    write_composition_files(out)
    _with_surfaces(out, {"wall 1": ["Wall_0_0"], "floor": ["Floor", "Wall_0_0"], "ceiling": ["Ceiling"]})
    with pytest.raises(VerificationError, match="'Wall_0_0' more than once"):
        verify_composition(out)


def test_a_composition_without_a_model_fails(tmp_path: Path) -> None:
    out = tmp_path / "out"
    write_composition_files(out)
    (out / "model.glb").unlink()
    with pytest.raises(VerificationError, match="missing \\['model.glb'\\]"):
        verify_composition(out)
