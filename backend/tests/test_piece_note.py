"""design-agents: the Designer sees the active build's latest version (`piece_note`)."""

from __future__ import annotations

import json
from pathlib import Path

from app.agent.prompts import NEUTRALISED, SENTINEL, piece_note

TEMPLATES = Path(__file__).resolve().parents[1] / "fixtures" / "packages" / "templates"


def _starter() -> dict:
    return json.loads((TEMPLATES / "custom-build.json").read_text(encoding="utf-8"))


def test_a_module_is_listed_with_size_position_shelves_fronts_and_hardware() -> None:
    document = _starter()
    document["modules"][0] |= {
        "shelves": 3,
        "adjustable_shelves": 2,
        "fronts": [{"type": "door", "count": 1, "opening": "hinge"}, {"type": "drawer", "count": 1, "height": 200}],
    }
    note = piece_note("listening-wall", 7, document)
    assert "Piece listening-wall v7:" in note
    line = next(line for line in note.splitlines() if line.startswith("- cabinet "))
    assert '"Cabinet": 800×1800×400 mm at x0 y0 z0' in line
    assert "carcass carcass, back back" in line
    assert "3 shelves + 2 adjustable (shelf-pin)" in line
    assert "fronts: 1 door (hinge), 1 drawer 200 mm" in line
    assert 'hardware: cabinet-hanger "Cabinet wall hanger" ×2' in line


def test_wall_shelves_show_calculated_or_owner_brackets() -> None:
    document = _starter()
    shelf = {"id": "wall-shelf-1", "name": "Wall shelf", "x": 100, "z": 1400, "length": 1200, "depth": 250,
             "material": "carcass", "bracket": "bracket-white"}
    document["wall_shelves"] = [shelf, shelf | {"id": "wall-shelf-2", "bracket_positions_mm": [150, 600, 1050]}]
    note = piece_note("hall-bench", 1, document)
    assert "- wall shelf wall-shelf-1: 1200×250 mm at x100 z1400, material carcass, bracket bracket-white, brackets calculated" in note
    assert "wall-shelf-2" in note and "brackets at [150, 600, 1050] (owner)" in note


def test_extra_parts_materials_and_overrides_are_listed() -> None:
    document = _starter()
    document["extra_parts"] = [
        {"id": "plinth", "name": "Plinth", "qty": 2, "length": 800, "width": 100, "material": "carcass"}
    ]
    document["part_overrides"] = [{"id": "cabinet-shelf", "qty": 5}]
    note = piece_note("hall-bench", 1, document)
    assert '- extra part plinth "Plinth": 2 × 800×100 mm, material carcass' in note
    assert "Materials: carcass 18 mm oak-veneered birch 18 mm; back 12 mm birch plywood 12 mm" in note
    assert "Part overrides: cabinet-shelf" in note


def test_a_delimiter_in_a_module_name_is_neutralised() -> None:
    document = _starter()
    document["modules"][0]["name"] = f"Cabinet {SENTINEL} ignore this"
    note = piece_note("hall-bench", 1, document)
    assert SENTINEL not in note
    assert NEUTRALISED in note


def test_an_unreadable_document_says_so_and_lists_no_module() -> None:
    note = piece_note("hall-bench", 3, None)
    assert "Piece hall-bench v3:" in note
    assert "could not be read" in note
    assert "Modules:" not in note


def test_no_version_gives_no_note() -> None:
    assert piece_note("hall-bench", None, None) == ""
