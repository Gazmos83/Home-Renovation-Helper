"""hardware-drilling: a version freezes the data sheets and bracket rules it was calculated from."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.blender import storage
from app.blender.custom_build.derive import drilling, emitted_spec
from app.db.session import make_engine
from app.guidelines import datasheets
from app.guidelines.hardware_inputs import freeze_inputs
from app.guidelines.rules import RuleSource
from app.packages import service
from tests.drill_helpers import COUNT_TABLE, build, module, wall_shelf

pytestmark = pytest.mark.usefixtures("clean_chunks")

SOURCE = RuleSource(publication="topnotch-shelf-brackets", section="Where?", quote="10cm to 20cm")
HINGE_PAGE = "https://www.toom.de/p/hinge/1"


def _rule(check: str, params: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"rule-{check}", check=check, source=SOURCE,
        params=SimpleNamespace(model_dump=lambda mode="json", p=params: p),
    )


RULES = (
    _rule("shelf_bracket_count_for_length", {"table": COUNT_TABLE}),
    _rule("shelf_bracket_spacing_mm", {"end_distance_mm": {"min": 100, "max": 200}, "even_tolerance_mm": 10}),
    _rule("height_range_mm", {"match": ["x"], "min_mm": 1, "max_mm": 2}),
)

SPEC = build(
    modules=[module(adjustable_shelves=2, fronts=[{"type": "door", "count": 1, "opening": "hinge"}])],
    wall_shelves=[wall_shelf()],
)


@pytest.fixture
def session(migrated_database: str, fake_embedder) -> Iterator[Session]:
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        session.execute(text("DELETE FROM hardware_data_sheets"))
        session.commit()
        yield session
        session.rollback()
        session.execute(text("DELETE FROM hardware_data_sheets"))
        session.commit()
    engine.dispose()


def _sheet(session: Session, key: str, kind: str, values: dict, **fields) -> None:
    datasheets.create_sheet(
        session, frozenset({"toom"}), key=key, kind=kind, maker="Hettich", model=key, values=values,
        source_kind="toom", page_url=f"https://www.toom.de/p/{key}/1", **fields,
    )
    session.commit()


def test_the_file_holds_only_the_named_keys_and_both_bracket_rules(session: Session) -> None:
    _sheet(session, "hinge-concealed-110", "hinge", {"cup_diameter_mm": {"value": 35}})
    _sheet(session, "shelf-pin", "shelf_pin", {"pitch_mm": {"value": 32}})
    _sheet(session, "unrelated", "hinge", {"cup_diameter_mm": {"value": 26}})
    frozen = freeze_inputs(session, RULES, SPEC)
    assert sorted(frozen["data_sheets"]) == ["hinge-concealed-110", "shelf-pin"]
    assert sorted(frozen["rules"]) == ["shelf_bracket_count_for_length", "shelf_bracket_spacing_mm"]
    sheet = frozen["data_sheets"]["shelf-pin"]
    assert sheet["values"] == {"pitch_mm": {"value": 32}} and sheet["source"].startswith("https://www.toom.de")
    assert sheet["updated_at"]
    assert frozen["rules"]["shelf_bracket_spacing_mm"]["source"]["publication"] == "topnotch-shelf-brackets"


def test_a_named_plate_sheet_is_frozen_with_its_hinge(session: Session) -> None:
    _sheet(session, "hinge-concealed-110", "hinge", {"plate_item": "plate-110"})
    _sheet(session, "plate-110", "hinge", {})
    assert sorted(freeze_inputs(session, (), SPEC)["data_sheets"]) == ["hinge-concealed-110", "plate-110"]


def test_editing_a_sheet_afterwards_leaves_the_versions_list_unchanged(session: Session, tmp_path: Path) -> None:
    _sheet(session, "hinge-concealed-110", "hinge", {"cup_edge_distance_mm": {"value": 5}, "end_distance_mm": {"value": 100}})
    created = service.create_version(
        tmp_path, "cab", SPEC, lambda version: None, inputs=freeze_inputs(session, RULES, SPEC)
    )
    folder = storage.version_dir(tmp_path, "cab", created["version"])
    before = drilling(SPEC, storage.read_hardware_inputs(folder))

    sheet = datasheets.list_sheets(session)[0]
    datasheets.update_sheet(
        session, frozenset({"toom"}), sheet.id, kind="hinge", maker="Hettich", model=sheet.key,
        values={"cup_edge_distance_mm": {"value": 9}, "end_distance_mm": {"value": 100}},
        source_kind="toom", page_url=sheet.page_url,
    )
    session.commit()

    assert drilling(SPEC, storage.read_hardware_inputs(folder)) == before
    newer = freeze_inputs(session, RULES, SPEC)
    assert newer["data_sheets"]["hinge-concealed-110"]["values"]["cup_edge_distance_mm"] == {"value": 9}


def test_a_version_without_the_file_derives_as_before_with_no_drilling(tmp_path: Path) -> None:
    created = service.create_version(tmp_path, "old", SPEC, lambda version: None)
    folder = storage.version_dir(tmp_path, "old", created["version"])
    assert not (folder / storage.HARDWARE_INPUTS_FILE).exists()
    assert storage.read_hardware_inputs(folder) is None
    assert "drilling" not in emitted_spec(SPEC, None)
    assert "drilling" in emitted_spec(SPEC, {"data_sheets": {}, "rules": {}})


def test_the_file_is_plain_json_next_to_the_input(tmp_path: Path) -> None:
    created = service.create_version(tmp_path, "cab", SPEC, lambda v: None, inputs={"data_sheets": {}, "rules": {}})
    folder = storage.version_dir(tmp_path, "cab", created["version"])
    assert json.loads((folder / storage.HARDWARE_INPUTS_FILE).read_text()) == {"data_sheets": {}, "rules": {}}
