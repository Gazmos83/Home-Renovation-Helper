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
from app.blender.custom_build.derive import derive, drilling, emitted_spec
from app.blender.hardware_catalog import default_catalog
from app.db.session import make_engine
from app.guidelines import datasheets
from app.guidelines.hardware_inputs import freeze_inputs
from app.guidelines.rule_overrides import file_items
from app.guidelines.rules import RuleSource, load_rules, parse_rules
from app.guidelines.sources import source_ids
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


def test_the_pin_and_hinge_count_rules_are_frozen_too(session: Session) -> None:
    pins = {"table": [{"max_width_mm": 914, "pins": 4}], "beyond": 5}
    hinges = {"table": [{"max_height_mm": 1016, "hinges": 2}], "beyond": 3}
    rules = (*RULES, _rule("shelf_pin_count_for_width", pins), _rule("hinge_count_for_height", hinges))
    frozen = freeze_inputs(session, rules, SPEC)
    assert sorted(frozen["rules"]) == [
        "hinge_count_for_height", "shelf_bracket_count_for_length", "shelf_bracket_spacing_mm", "shelf_pin_count_for_width",
    ]
    assert frozen["rules"]["shelf_pin_count_for_width"] == {
        "rule_id": "rule-shelf_pin_count_for_width", "params": pins,
        "source": {"publication": "topnotch-shelf-brackets", "section": "Where?", "quote": "10cm to 20cm"},
    }
    assert frozen["rules"]["hinge_count_for_height"]["params"] == hinges


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


def test_editing_the_hinge_count_rule_afterwards_leaves_the_version_unchanged(session: Session, tmp_path: Path) -> None:
    shipped = load_rules()
    created = service.create_version(tmp_path, "hall-cabinet", SPEC, lambda version: None,
                                     inputs=freeze_inputs(session, shipped, SPEC))
    folder = storage.version_dir(tmp_path, "hall-cabinet", created["version"])
    before = (drilling(SPEC, storage.read_hardware_inputs(folder)), derive(SPEC, storage.read_hardware_inputs(folder))[1])
    assert before[0]["counts"]["hinge_cup_borings"] == 2

    items = [item for item in file_items() if item["id"] != "hinge-count"]
    edited = next(item for item in file_items() if item["id"] == "hinge-count")
    edited["params"] = {"table": [{"max_height_mm": 1000, "hinges": 3}], "beyond": 4}
    newer_rules = parse_rules([*items, edited], source_ids())

    frozen = storage.read_hardware_inputs(folder)
    assert (drilling(SPEC, frozen), derive(SPEC, frozen)[1]) == before
    newer = freeze_inputs(session, newer_rules, SPEC)
    assert newer["rules"]["hinge_count_for_height"]["params"]["table"] == [{"max_height_mm": 1000, "hinges": 3}]
    assert drilling(SPEC, newer)["counts"]["hinge_cup_borings"] == 3


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


def test_the_rail_support_rule_and_the_hardware_catalog_are_frozen(session: Session) -> None:
    supports = {"table": [{"max_length_mm": 1000, "supports": 2}], "beyond": 3}
    frozen = freeze_inputs(session, (*RULES, _rule("rail_support_count_for_length", supports)), SPEC)
    assert frozen["rules"]["rail_support_count_for_length"]["params"] == supports
    assert frozen["hardware_catalog"] == default_catalog().frozen()
