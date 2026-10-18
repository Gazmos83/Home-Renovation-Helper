"""house-file: rooms, preferences, pieces and versions, extension requests, threads."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.agent import house_file
from app.agent.house_file import HouseFileError

LIVING = [[0, 0], [4000, 0], [4000, 3500], [0, 3500]]


def test_a_room_is_stored_and_read_by_name(db_session) -> None:
    house_file.upsert_room(
        db_session,
        "Living room",
        LIVING,
        2600,
        openings=[{"wall": 1, "type": "door", "offset_mm": 500, "width_mm": 900, "height_mm": 2100}],
    )
    room = house_file.room_by_name(db_session, "Living room")
    assert room is not None
    assert room.height_mm == 2600
    assert room.corners_mm == LIVING
    assert room.openings[0]["wall"] == 1
    assert room.openings[0]["sill_mm"] == 0


def test_a_door_with_a_sill_is_refused_by_name_and_nothing_is_stored(db_session) -> None:
    with pytest.raises(HouseFileError, match=r"openings\[0\] is a door and must not have a sill"):
        house_file.upsert_room(
            db_session,
            "Hall",
            LIVING,
            2600,
            openings=[
                {"wall": 0, "type": "door", "offset_mm": 0, "width_mm": 900, "height_mm": 2100, "sill_mm": 50}
            ],
        )
    assert house_file.room_by_name(db_session, "Hall") is None


def test_an_l_shaped_room_is_stored_counter_clockwise(db_session) -> None:
    l_shape = [[0, 0], [4000, 0], [4000, 2000], [2000, 2000], [2000, 4000], [0, 4000]]
    house_file.upsert_room(db_session, "L-room", list(reversed(l_shape)), 2600)
    room = house_file.room_by_name(db_session, "L-room")
    assert len(room.corners_mm) == 6
    assert room.corners_mm == l_shape or sorted(room.corners_mm) == sorted(l_shape)


def test_a_bow_tie_outline_is_refused_naming_the_outline(db_session) -> None:
    with pytest.raises(HouseFileError, match="simple outline"):
        house_file.upsert_room(db_session, "Bow", [[0, 0], [4000, 2000], [4000, 0], [0, 3500]], 2600)
    assert house_file.room_by_name(db_session, "Bow") is None


def test_an_opening_above_the_ceiling_is_refused() -> None:
    with pytest.raises(HouseFileError, match="above the ceiling"):
        house_file.validate_room(
            "Hall",
            LIVING,
            2400,
            openings=[
                {"wall": 0, "type": "window", "offset_mm": 100, "width_mm": 800, "height_mm": 1500, "sill_mm": 1200}
            ],
        )


def test_a_room_name_is_unique_and_a_second_write_replaces_the_measurements(db_session) -> None:
    first = house_file.upsert_room(db_session, "Study", LIVING, 2600)
    second = house_file.upsert_room(db_session, "Study", [[0, 0], [3000, 0], [3000, 3000], [0, 3000]], 2500)
    assert second.id == first.id
    assert [room.name for room in house_file.rooms(db_session)].count("Study") == 1
    assert house_file.room_by_name(db_session, "Study").height_mm == 2500


def test_the_room_name_constraint_is_in_the_database(db_session) -> None:
    from app.db.models import Room

    db_session.add(Room(name="Dup", corners_mm=LIVING, height_mm=2600, wall_thickness_mm=100, openings=[]))
    db_session.flush()
    db_session.add(Room(name="Dup", corners_mm=LIVING, height_mm=2600, wall_thickness_mm=100, openings=[]))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_preferences_are_named_values_and_a_later_write_replaces(db_session) -> None:
    house_file.set_preference(db_session, "style", "light oak")
    house_file.set_preference(db_session, "style", "light oak, no visible hardware")
    house_file.set_preference(db_session, "budget_eur", "400")
    found = house_file.preferences(db_session)
    assert found["style"] == "light oak, no visible hardware"
    assert found["budget_eur"] == "400"


def test_a_piece_with_a_first_version_and_a_revision(db_session, render_root: Path) -> None:
    house_file.record_piece(db_session, "hall-bench", "Hall bench", {"budget_eur": 400})
    house_file.record_version(db_session, "hall-bench", 1)
    house_file.record_version(db_session, "hall-bench", 2, revised_from=1, changes=["cabinet: shelves 2 → 3"])
    (render_root / "hall-bench" / "v1").mkdir(parents=True)
    (render_root / "hall-bench" / "v2").mkdir(parents=True)

    listing = {p["package_id"]: p for p in house_file.pieces(db_session, render_root)}
    piece = listing["hall-bench"]
    assert piece["has_brief"] is True
    assert piece["latest_version"] == 2
    first, second = piece["versions"]
    assert first["revised_from"] is None
    assert second["revised_from"] == 1
    assert second["changes"] == ["cabinet: shelves 2 → 3"]


def test_a_piece_cannot_be_recorded_twice(db_session) -> None:
    house_file.record_piece(db_session, "twice", "Twice")
    with pytest.raises(HouseFileError, match="already recorded"):
        house_file.record_piece(db_session, "twice", "Twice")


def test_a_folder_only_package_is_listed_without_a_brief(db_session, render_root: Path) -> None:
    folder = render_root / "direct-shelf" / "v1"
    folder.mkdir(parents=True)
    (folder / "status.json").write_text(json.dumps({"status": "succeeded"}), encoding="utf-8")

    listing = {p["package_id"]: p for p in house_file.pieces(db_session, render_root)}
    piece = listing["direct-shelf"]
    assert piece["has_brief"] is False
    assert piece["latest_version"] == 1
    assert piece["status"] == "succeeded"


def test_an_extension_request_round_trips(db_session) -> None:
    house_file.record_extension_request(
        db_session, "modules[0].bevel_mm", "a bevelled front edge please", package_id="hall-bench"
    )
    opened = [r for r in house_file.open_extension_requests(db_session) if r.field == "modules[0].bevel_mm"]
    assert len(opened) == 1
    assert opened[0].request == "a bevelled front edge please"
    assert opened[0].package_id == "hall-bench"
    assert opened[0].status == "open"


def test_threads_are_listed_newest_activity_first(db_session) -> None:
    older = house_file.create_thread(db_session, "Hall bench")
    newer = house_file.create_thread(db_session, "Desk")
    time.sleep(0.01)
    house_file.touch_thread(db_session, older.id, package_id="hall-bench")

    ids = [t.id for t in house_file.list_threads(db_session)]
    assert ids.index(older.id) < ids.index(newer.id)
    assert house_file.get_thread(db_session, older.id).package_id == "hall-bench"


# --- apartments -------------------------------------------------------------------------

LIVING_ROOM = {
    "name": "Living room", "corners_mm": [[0, 0], [5200, 0], [5200, 3800], [0, 3800]],
    "openings": [{"wall": 1, "type": "door", "offset_mm": 1200, "width_mm": 900, "height_mm": 2050}],
}
BEDROOM = {"name": "Bedroom", "corners_mm": [[5200, 0], [8400, 0], [8400, 3800], [5200, 3800]]}


def test_an_apartment_stores_its_rooms_in_one_plan_frame(db_session) -> None:
    apartment = house_file.upsert_apartment(db_session, "Flat", 2550, 120, [LIVING_ROOM, BEDROOM])
    rooms = house_file.rooms_of(db_session, apartment)
    assert [r.name for r in rooms] == ["Bedroom", "Living room"]
    assert all(r.apartment_id == apartment.id for r in rooms)
    assert rooms[0].height_mm == 2550 and rooms[0].wall_thickness_mm == 120
    described = house_file.describe_apartment(db_session, apartment)
    assert described["name"] == "Flat" and len(described["rooms"]) == 2


def test_overlapping_rooms_refuse_the_apartment_naming_both_and_store_nothing(db_session) -> None:
    overlapping = {**BEDROOM, "corners_mm": [[5000, 0], [8400, 0], [8400, 3800], [5000, 3800]]}
    with pytest.raises(HouseFileError, match="rooms 'Living room' and 'Bedroom' overlap"):
        house_file.upsert_apartment(db_session, "Flat", 2550, 120, [LIVING_ROOM, overlapping])
    assert house_file.apartment_by_name(db_session, "Flat") is None
    assert house_file.room_by_name(db_session, "Living room") is None


def test_a_second_write_replaces_a_room_and_checks_it_against_the_ones_kept(db_session) -> None:
    house_file.upsert_apartment(db_session, "Flat", 2550, 120, [LIVING_ROOM, BEDROOM])
    wider = {**BEDROOM, "corners_mm": [[5200, 0], [9000, 0], [9000, 3800], [5200, 3800]]}
    house_file.upsert_apartment(db_session, "Flat", 2550, 120, [wider])
    assert house_file.room_by_name(db_session, "Bedroom").corners_mm[1] == [9000, 0]
    clashing = {**BEDROOM, "corners_mm": [[4000, 0], [9000, 0], [9000, 3800], [4000, 3800]]}
    with pytest.raises(HouseFileError, match="overlap"):
        house_file.upsert_apartment(db_session, "Flat", 2550, 120, [clashing])


# --- version approval ---------------------------------------------------------


def _bench_with_versions(db_session, count: int = 3) -> None:
    house_file.record_piece(db_session, "hall-bench", "Hall bench")
    for number in range(1, count + 1):
        house_file.record_version(db_session, "hall-bench", number, revised_from=number - 1 or None)


def test_a_new_version_starts_unapproved(db_session) -> None:
    _bench_with_versions(db_session, 1)
    assert house_file.approved_version_of(db_session, "hall-bench") is None


def test_approving_a_version_moves_the_approval(db_session, render_root: Path) -> None:
    _bench_with_versions(db_session)
    house_file.approve_version(db_session, "hall-bench", 2)
    assert house_file.approved_version_of(db_session, "hall-bench") == 2
    house_file.approve_version(db_session, "hall-bench", 3)
    assert house_file.approved_version_of(db_session, "hall-bench") == 3
    listed = house_file.pieces(db_session, render_root)[0]
    assert listed["approved_version"] == 3
    assert [v["approved_at"] is not None for v in listed["versions"]] == [False, False, True]


def test_approving_and_unapproving_are_idempotent(db_session) -> None:
    _bench_with_versions(db_session, 2)
    first = house_file.approve_version(db_session, "hall-bench", 1).approved_at
    assert house_file.approve_version(db_session, "hall-bench", 1).approved_at == first
    house_file.unapprove_version(db_session, "hall-bench", 1)
    house_file.unapprove_version(db_session, "hall-bench", 1)
    house_file.unapprove_version(db_session, "hall-bench", 2)
    assert house_file.approved_version_of(db_session, "hall-bench") is None


def test_a_revision_creates_an_unapproved_version_and_keeps_the_approval(db_session) -> None:
    _bench_with_versions(db_session, 2)
    house_file.approve_version(db_session, "hall-bench", 2)
    house_file.record_version(db_session, "hall-bench", 3, revised_from=2, changes=["shelves 2 → 3"])
    assert house_file.version_row(db_session, "hall-bench", 3).approved_at is None
    assert house_file.approved_version_of(db_session, "hall-bench") == 2


def test_a_version_with_no_record_cannot_be_approved(db_session) -> None:
    house_file.record_piece(db_session, "hall-bench", "Hall bench")
    with pytest.raises(HouseFileError, match="not recorded"):
        house_file.approve_version(db_session, "hall-bench", 1)
    with pytest.raises(HouseFileError, match="not recorded"):
        house_file.unapprove_version(db_session, "hall-bench", 1)


def test_the_house_note_names_the_approved_version_or_none(db_session, render_root: Path) -> None:
    from app.agent.prompts import house_note

    _bench_with_versions(db_session, 2)
    note = house_note([], {}, house_file.pieces(db_session, render_root), [])
    assert "hall-bench (Hall bench): v2, approved: none" in note
    house_file.approve_version(db_session, "hall-bench", 1)
    note = house_note([], {}, house_file.pieces(db_session, render_root), [])
    assert "hall-bench (Hall bench): v2, approved: v1" in note


# --- room compositions ------------------------------------------------------------------


def _composition_folder(render_root: Path, slug: str, version: int, items: list[dict]) -> None:
    from app.blender import storage

    folder = storage.composition_version_dir(render_root, slug, version)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(
        json.dumps({"kind": "room_composition", "scope": {"room": "Wohnen"}, "items": items}), encoding="utf-8"
    )
    storage.write_status(folder, status="succeeded")


def test_a_confirmed_composition_is_recorded_with_its_version(db_session, render_root: Path) -> None:
    composition = house_file.record_composition(db_session, "room", "Wohnen")
    assert composition.slug == "wohnen"
    assert house_file.record_composition(db_session, "room", "Wohnen").id == composition.id
    house_file.record_composition_version(db_session, composition, 1, None, ["placed: sofa"])
    _composition_folder(render_root, "wohnen", 1, [{"id": "sofa", "type": "stand-in", "name": "Sofa"}])
    listed = house_file.compositions(db_session, render_root)
    assert listed == [{
        "scope": "room", "name": "Wohnen", "slug": "wohnen", "latest_version": 1, "status": "succeeded",
        "items": [{"id": "sofa", "type": "stand-in", "name": "Sofa"}], "versions": [1],
        "approved_version": None,
    }]


def test_a_placed_piece_unapproved_later_is_kept_and_marked(db_session, render_root: Path) -> None:
    house_file.record_piece(db_session, "listening-wall", "Listening wall")
    house_file.record_version(db_session, "listening-wall", 4)
    house_file.approve_version(db_session, "listening-wall", 4)
    composition = house_file.record_composition(db_session, "room", "Wohnen")
    house_file.record_composition_version(db_session, composition, 1, None, [])
    _composition_folder(render_root, "wohnen", 1, [
        {"id": "listening-wall", "type": "piece", "package_id": "listening-wall", "version": 4},
    ])
    item = house_file.compositions(db_session, render_root)[0]["items"][0]
    assert item["approved"] is True and item["no_longer_approved"] is False

    house_file.unapprove_version(db_session, "listening-wall", 4)
    item = house_file.compositions(db_session, render_root)[0]["items"][0]
    assert item["name"] == "listening-wall v4"
    assert item["approved"] is False and item["no_longer_approved"] is True


def _reset_house(db_session) -> None:
    from tests.conftest import clean_house_file

    clean_house_file(db_session.get_bind())
    db_session.expire_all()


@pytest.fixture
def isolated_house(db_session):
    """A house file that truncates around tests that commit (composition version delete)."""
    db_session.rollback()
    _reset_house(db_session)
    yield db_session
    db_session.rollback()
    _reset_house(db_session)


def _wohnen(
    db_session,
    render_root: Path,
    *,
    versions: tuple[int, ...] = (1,),
    items: list[dict] | None = None,
    piece_approved: bool = True,
):
    house_file.record_piece(db_session, "listening-wall", "Listening wall")
    house_file.record_version(db_session, "listening-wall", 4)
    if piece_approved:
        house_file.approve_version(db_session, "listening-wall", 4)
    composition = house_file.record_composition(db_session, "room", "Wohnen")
    placed = items or [
        {"id": "listening-wall", "type": "piece", "package_id": "listening-wall", "version": 4},
    ]
    for number in versions:
        house_file.record_composition_version(
            db_session, composition, number, number - 1 if number > 1 else None, []
        )
        _composition_folder(render_root, "wohnen", number, placed)
    return composition


def test_approving_a_composition_version_moves_the_approval(isolated_house, render_root: Path) -> None:
    db_session = isolated_house
    _wohnen(db_session, render_root, versions=(1, 2, 3))
    composition = house_file.composition_by_slug(db_session, "wohnen")
    house_file.approve_composition_version(db_session, render_root, "wohnen", 2)
    assert house_file.approved_composition_version_of(db_session, composition.id) == 2
    house_file.approve_composition_version(db_session, render_root, "wohnen", 3)
    assert house_file.approved_composition_version_of(db_session, composition.id) == 3
    listed = house_file.compositions(db_session, render_root)[0]
    assert listed["approved_version"] == 3


def test_approving_and_unapproving_a_composition_version_are_idempotent(
    isolated_house, render_root: Path
) -> None:
    db_session = isolated_house
    _wohnen(db_session, render_root, versions=(1, 2))
    first = house_file.approve_composition_version(db_session, render_root, "wohnen", 1).approved_at
    assert house_file.approve_composition_version(db_session, render_root, "wohnen", 1).approved_at == first
    house_file.unapprove_composition_version(db_session, "wohnen", 1)
    house_file.unapprove_composition_version(db_session, "wohnen", 1)
    house_file.unapprove_composition_version(db_session, "wohnen", 2)
    composition = house_file.composition_by_slug(db_session, "wohnen")
    assert house_file.approved_composition_version_of(db_session, composition.id) is None


def test_a_new_composition_version_stays_unapproved(isolated_house, render_root: Path) -> None:
    db_session = isolated_house
    composition = _wohnen(db_session, render_root, versions=(1,))
    house_file.approve_composition_version(db_session, render_root, "wohnen", 1)
    house_file.record_composition_version(db_session, composition, 2, 1, ["placed: sofa"])
    _composition_folder(render_root, "wohnen", 2, [{"id": "sofa", "type": "stand-in", "name": "Sofa"}])
    assert house_file.composition_version_row(db_session, composition.id, 2).approved_at is None
    assert house_file.approved_composition_version_of(db_session, composition.id) == 1
    listed = house_file.compositions(db_session, render_root)[0]
    assert listed["approved_version"] == 1 and listed["latest_version"] == 2


def test_the_approved_versions_items_are_listed_beside_a_newer_drafts(isolated_house, render_root: Path) -> None:
    db_session = isolated_house
    composition = _wohnen(db_session, render_root, versions=(1,), items=[
        {"id": "sofa", "type": "model", "model_id": "m1", "name": "Sofa Lund",
         "width_mm": 2200, "depth_mm": 950, "height_mm": 850, "placement": {"wall": 1, "offset_mm": 400}},
    ])
    house_file.approve_composition_version(db_session, render_root, "wohnen", 1)
    house_file.record_composition_version(db_session, composition, 2, 1, ["removed: sofa"])
    _composition_folder(render_root, "wohnen", 2, [])
    listed = house_file.compositions(db_session, render_root)[0]
    assert listed["items"] == []
    assert listed["approved_items"] == [{
        "id": "sofa", "type": "model", "name": "Sofa Lund", "placement": {"wall": 1, "offset_mm": 400},
        "width_mm": 2200, "depth_mm": 950, "height_mm": 850,
    }]


def test_no_approved_version_gives_no_approved_items(isolated_house, render_root: Path) -> None:
    db_session = isolated_house
    _wohnen(db_session, render_root, versions=(1, 2))
    assert "approved_items" not in house_file.compositions(db_session, render_root)[0]


def test_an_unreadable_approved_file_gives_no_items(isolated_house, render_root: Path) -> None:
    from app.blender import storage

    db_session = isolated_house
    composition = _wohnen(db_session, render_root, versions=(1,))
    house_file.approve_composition_version(db_session, render_root, "wohnen", 1)
    house_file.record_composition_version(db_session, composition, 2, 1, [])
    _composition_folder(render_root, "wohnen", 2, [{"id": "sofa", "type": "stand-in", "name": "Sofa"}])
    (storage.composition_version_dir(render_root, "wohnen", 1) / storage.INPUT_FILE).write_text("{", encoding="utf-8")
    listed = house_file.compositions(db_session, render_root)[0]
    assert listed["approved_items"] == [] and len(listed["items"]) == 1


def test_approving_a_composition_version_with_an_unapproved_piece_is_refused(
    isolated_house, render_root: Path
) -> None:
    db_session = isolated_house
    _wohnen(db_session, render_root, piece_approved=False)
    with pytest.raises(HouseFileError, match="listening-wall v4.*not approved"):
        house_file.approve_composition_version(db_session, render_root, "wohnen", 1)
    composition = house_file.composition_by_slug(db_session, "wohnen")
    assert house_file.approved_composition_version_of(db_session, composition.id) is None


def test_the_composition_note_names_the_approved_version_or_none(isolated_house, render_root: Path) -> None:
    from app.agent.prompts import composition_note

    db_session = isolated_house
    _wohnen(db_session, render_root, versions=(1, 2))
    note = composition_note(house_file.compositions(db_session, render_root))
    assert "room Wohnen: v2, succeeded, approved: none" in note
    house_file.approve_composition_version(db_session, render_root, "wohnen", 2)
    note = composition_note(house_file.compositions(db_session, render_root))
    assert "room Wohnen: v2, succeeded, approved: v2" in note


def test_the_composition_note_says_where_each_item_stands(isolated_house, render_root: Path) -> None:
    from app.agent.prompts import composition_note

    db_session = isolated_house
    _wohnen(db_session, render_root, items=[
        {"id": "listening-wall", "type": "piece", "package_id": "listening-wall", "version": 4,
         "placement": {"wall": 0, "offset_mm": 300}},
        {"id": "sofa", "type": "stand-in", "name": "Sofa",
         "placement": {"x_mm": 2500, "y_mm": 2000, "rotation_deg": 90}},
    ])
    note = composition_note(house_file.compositions(db_session, render_root))
    assert "listening-wall (piece: listening-wall v4) on wall 1 (index 0) at offset 300 mm" in note
    assert "sofa (stand-in: Sofa) free at x 2500, y 2000 mm, rotated 90°" in note


def test_the_composition_note_marks_a_floor_layer_item(isolated_house, render_root: Path) -> None:
    from app.agent.prompts import composition_note

    db_session = isolated_house
    _wohnen(db_session, render_root, items=[
        {"id": "rug", "type": "stand-in", "name": "Rug", "layer": "floor",
         "placement": {"x_mm": 2500, "y_mm": 2300, "rotation_deg": 0}},
    ])
    note = composition_note(house_file.compositions(db_session, render_root))
    assert "rug (stand-in: Rug) (floor layer) free at x 2500, y 2300 mm, rotated 0°" in note


def test_the_composition_note_marks_a_ceiling_layer_item(isolated_house, render_root: Path) -> None:
    from app.agent.prompts import composition_note

    db_session = isolated_house
    _wohnen(db_session, render_root, items=[
        {"id": "pendant", "type": "model", "name": "Pendelleuchte Calisto", "layer": "ceiling",
         "placement": {"x_mm": 2500, "y_mm": 1200, "rotation_deg": 0}},
    ])
    note = composition_note(house_file.compositions(db_session, render_root))
    assert "pendant (model: Pendelleuchte Calisto) (ceiling layer) free at x 2500, y 1200 mm, rotated 0°" in note


def test_unapproving_a_piece_in_an_approved_room_is_refused(isolated_house, render_root: Path) -> None:
    db_session = isolated_house
    composition = _wohnen(db_session, render_root)
    house_file.approve_composition_version(db_session, render_root, "wohnen", 1)
    with pytest.raises(HouseFileError, match="Wohnen version 1"):
        house_file.unapprove_version(db_session, "listening-wall", 4, root=render_root)
    assert house_file.approved_version_of(db_session, "listening-wall") == 4
    assert house_file.approved_composition_version_of(db_session, composition.id) == 1


def test_unapproving_a_piece_in_an_unapproved_room_still_clears(isolated_house, render_root: Path) -> None:
    db_session = isolated_house
    composition = _wohnen(db_session, render_root)
    house_file.unapprove_version(db_session, "listening-wall", 4, root=render_root)
    assert house_file.approved_version_of(db_session, "listening-wall") is None
    assert house_file.approved_composition_version_of(db_session, composition.id) is None


def test_deleting_an_approved_composition_version_is_refused(isolated_house, render_root: Path) -> None:
    from app.blender import storage as blender_storage

    db_session = isolated_house
    _wohnen(db_session, render_root, versions=(1, 2))
    house_file.approve_composition_version(db_session, render_root, "wohnen", 2)
    with pytest.raises(HouseFileError, match="unapprove version 2 first"):
        house_file.delete_composition_version(db_session, render_root, "wohnen", 2)
    assert blender_storage.composition_versions(render_root, "wohnen") == [1, 2]
    assert house_file.composition_version_row(
        db_session, house_file.composition_by_slug(db_session, "wohnen").id, 2
    ) is not None


@pytest.mark.parametrize("status", ["queued", "running"])
def test_deleting_a_composition_version_still_building_is_refused(
    isolated_house, render_root: Path, status: str
) -> None:
    from app.blender import storage as blender_storage

    db_session = isolated_house
    _wohnen(db_session, render_root, versions=(1, 2))
    blender_storage.write_status(
        blender_storage.composition_version_dir(render_root, "wohnen", 2), status=status
    )
    with pytest.raises(HouseFileError, match="still building"):
        house_file.delete_composition_version(db_session, render_root, "wohnen", 2)
    assert blender_storage.composition_versions(render_root, "wohnen") == [1, 2]


def test_deleting_a_composition_version_still_rendering_is_refused(
    isolated_house, render_root: Path
) -> None:
    from app.blender import storage as blender_storage

    db_session = isolated_house
    _wohnen(db_session, render_root, versions=(1, 2))
    blender_storage.write_render_status(
        blender_storage.composition_version_dir(render_root, "wohnen", 2), "still", status="queued"
    )
    with pytest.raises(HouseFileError, match="still rendering"):
        house_file.delete_composition_version(db_session, render_root, "wohnen", 2)


def test_deleting_a_missing_composition_version_is_refused(isolated_house, render_root: Path) -> None:
    from app.agent.house_file import VersionMissing

    db_session = isolated_house
    _wohnen(db_session, render_root)
    with pytest.raises(VersionMissing):
        house_file.delete_composition_version(db_session, render_root, "wohnen", 9)
    with pytest.raises(VersionMissing):
        house_file.delete_composition_version(db_session, render_root, "nothing-here", 1)


def test_deleting_an_older_composition_version_does_not_reuse_its_number(
    isolated_house, render_root: Path
) -> None:
    from app.blender import storage as blender_storage

    db_session = isolated_house
    _wohnen(db_session, render_root, versions=(1, 2))
    assert house_file.delete_composition_version(db_session, render_root, "wohnen", 2) is False
    db_session.expire_all()
    assert blender_storage.composition_versions(render_root, "wohnen") == [1]
    assert house_file.composition_by_slug(db_session, "wohnen") is not None
    assert blender_storage.next_composition_version(render_root, "wohnen") == 3


def test_deleting_the_last_composition_version_keeps_the_measured_room(
    isolated_house, render_root: Path
) -> None:
    from app.blender import storage as blender_storage

    db_session = isolated_house
    _wohnen(db_session, render_root)
    house_file.upsert_room(db_session, "Wohnen", LIVING, 2600)
    assert house_file.delete_composition_version(db_session, render_root, "wohnen", 1) is True
    db_session.expire_all()
    assert house_file.composition_by_slug(db_session, "wohnen") is None
    assert house_file.room_by_name(db_session, "Wohnen") is not None
    assert blender_storage.composition_versions(render_root, "wohnen") == []
    assert blender_storage.next_composition_version(render_root, "wohnen") == 1


def test_deleting_a_thread_takes_its_settings_and_upload_records_and_keeps_the_piece(db_session) -> None:
    from app.db.models import ThreadToolSetting, Upload

    house_file.record_piece(db_session, "hall-bench", "Hall bench")
    house_file.record_version(db_session, "hall-bench", 1)
    house_file.record_review(db_session, "hall-bench", 1, ["screenshot.png"], [])
    thread = house_file.create_thread(db_session, "Hall bench", package_id=None)
    house_file.touch_thread(db_session, thread.id, package_id="hall-bench")
    db_session.add(ThreadToolSetting(thread_id=thread.id, plugin="room_fit", enabled=False))
    db_session.add(Upload(thread_id=thread.id, kind="png", size_bytes=3, original_name="a.png"))
    db_session.flush()
    thread_id = thread.id
    db_session.expunge_all()

    assert house_file.delete_thread(db_session, thread_id) is True
    assert house_file.get_thread(db_session, thread_id) is None
    assert db_session.query(ThreadToolSetting).filter_by(thread_id=thread_id).count() == 0
    assert db_session.query(Upload).filter_by(thread_id=thread_id).count() == 0
    assert house_file.version_row(db_session, "hall-bench", 1) is not None
    assert len(house_file.reviews_for(db_session, "hall-bench", 1)) == 1
    assert house_file.delete_thread(db_session, thread_id) is False
    # A turn that touches a deleted thread changes nothing.
    house_file.touch_thread(db_session, thread_id, package_id="hall-bench")
    assert house_file.get_thread(db_session, thread_id) is None


def test_a_generated_title_never_replaces_the_owners(db_session) -> None:
    untitled = house_file.create_thread(db_session)
    assert house_file.set_title_if_empty(db_session, untitled.id, "  Listening wall for records ") is True
    db_session.expire_all()
    assert house_file.get_thread(db_session, untitled.id).title == "Listening wall for records"

    renamed = house_file.create_thread(db_session)
    assert house_file.set_title(db_session, renamed.id, "Listening wall") is True
    assert house_file.set_title_if_empty(db_session, renamed.id, "Record shelf plan") is False
    db_session.expire_all()
    assert house_file.get_thread(db_session, renamed.id).title == "Listening wall"


def test_renaming_an_unknown_thread_reports_it(db_session) -> None:
    from uuid import uuid4

    assert house_file.set_title(db_session, uuid4(), "Listening wall") is False


def test_a_summary_is_stored_and_goes_with_its_thread(db_session) -> None:
    thread = house_file.create_thread(db_session, "Hall bench")
    assert house_file.read_summary(db_session, thread.id) == (None, None)
    house_file.write_summary(db_session, thread.id, "Decisions so far: hall 1800 mm.", "message-12")
    db_session.expire_all()
    assert house_file.read_summary(db_session, thread.id) == ("Decisions so far: hall 1800 mm.", "message-12")

    thread_id = thread.id
    assert house_file.delete_thread(db_session, thread_id) is True
    assert house_file.read_summary(db_session, thread_id) == (None, None)


# --- a conversation's room and builds (conversation-projects) ----------------------------


def _hall(db_session):
    return house_file.upsert_room(db_session, "Hall", LIVING, 2600)


def test_a_declined_room_is_recorded_and_survives_a_later_room(db_session) -> None:
    from uuid import uuid4

    thread = house_file.create_thread(db_session, "Shoe bench")
    assert thread.room_declined is False
    assert house_file.decline_room(db_session, thread.id) is True
    assert house_file.get_thread(db_session, thread.id).room_declined is True
    house_file.set_thread_room(db_session, thread.id, _hall(db_session))
    assert house_file.get_thread(db_session, thread.id).room_declined is True
    assert house_file.decline_room(db_session, uuid4()) is False


def test_a_new_thread_has_no_confirmed_room(db_session) -> None:
    hall = _hall(db_session)
    first = house_file.create_thread(db_session, "First")
    house_file.set_thread_room(db_session, first.id, hall)
    second = house_file.create_thread(db_session, "Second")
    db_session.expire_all()

    assert house_file.thread_scope(db_session, first.id)[0].name == "Hall"
    assert house_file.thread_scope(db_session, second.id) == (None, None)


def test_a_thread_scope_is_a_room_or_an_apartment_never_both(db_session) -> None:
    from app.db.models import Apartment

    hall = _hall(db_session)
    thread = house_file.create_thread(db_session, "Scope")
    flat = Apartment(name="Scope flat", ceiling_height_mm=2600, wall_thickness_mm=100)
    db_session.add(flat)
    db_session.flush()

    house_file.set_thread_room(db_session, thread.id, hall)
    house_file.set_thread_apartment(db_session, thread.id, flat)
    db_session.expire_all()
    room, chosen = house_file.thread_scope(db_session, thread.id)
    assert room is None and chosen.name == "Scope flat"

    house_file.set_thread_room(db_session, thread.id, hall)
    db_session.expire_all()
    room, chosen = house_file.thread_scope(db_session, thread.id)
    assert room.name == "Hall" and chosen is None


def test_a_build_is_listed_once_and_set_active_does_not_switch_a_bound_thread(db_session) -> None:
    thread = house_file.create_thread(db_session, "Builds")
    house_file.touch_thread(db_session, thread.id, package_id="hall-bench")
    house_file.touch_thread(db_session, thread.id, package_id="hall-bench")
    house_file.set_active_build(db_session, thread.id, "shoe-rack")
    house_file.add_build(db_session, thread.id, "shoe-rack")
    db_session.expire_all()

    # Legacy add_build can still insert a row; the bound piece stays hall-bench.
    assert sorted(b.package_id for b in house_file.builds_of(db_session, thread.id)) == ["hall-bench", "shoe-rack"]
    assert house_file.get_thread(db_session, thread.id).package_id == "hall-bench"


def test_thread_id_for_piece_returns_the_bound_conversation(db_session) -> None:
    assert house_file.thread_id_for_piece(db_session, "hall-bench") is None
    older = house_file.create_thread(db_session, "Older", package_id="hall-bench")
    newer = house_file.create_thread(db_session, "Newer", package_id="hall-bench")
    house_file.touch_thread(db_session, newer.id)
    db_session.expire_all()

    assert house_file.thread_id_for_piece(db_session, "hall-bench") == newer.id
    assert house_file.thread_ids_for_pieces(db_session, ["hall-bench", "shoe-rack"]) == {
        "hall-bench": newer.id,
    }
    assert older.id != newer.id


def test_a_summary_is_kept_per_build(db_session) -> None:
    thread = house_file.create_thread(db_session, "Summaries")
    house_file.add_build(db_session, thread.id, "hall-bench")
    house_file.add_build(db_session, thread.id, "shoe-rack")
    house_file.write_summary(db_session, thread.id, "bench: oak", "m3", package_id="hall-bench")
    house_file.write_summary(db_session, thread.id, "rack: pine", "m5", package_id="shoe-rack")
    house_file.write_summary(db_session, thread.id, "no build yet", "m1")
    db_session.expire_all()

    assert house_file.read_summary(db_session, thread.id, "hall-bench") == ("bench: oak", "m3")
    assert house_file.read_summary(db_session, thread.id, "shoe-rack") == ("rack: pine", "m5")
    assert house_file.read_summary(db_session, thread.id) == ("no build yet", "m1")
    assert house_file.read_summary(db_session, thread.id, "other") == (None, None)


def test_deleting_a_thread_removes_its_builds_and_summaries_and_keeps_the_piece_room(db_session) -> None:
    from app.db.models import ThreadPiece

    hall = _hall(db_session)
    house_file.record_piece(db_session, "hall-bench", "Hall bench", room_id=hall.id)
    thread = house_file.create_thread(db_session, "Gone")
    house_file.touch_thread(db_session, thread.id, package_id="hall-bench")
    house_file.write_summary(db_session, thread.id, "bench: oak", "m3", package_id="hall-bench")
    thread_id = thread.id
    db_session.expunge_all()

    assert house_file.delete_thread(db_session, thread_id) is True
    assert db_session.query(ThreadPiece).filter_by(thread_id=thread_id).count() == 0
    from app.db.models import Piece

    assert db_session.get(Piece, "hall-bench").room_id == hall.id


def test_a_piece_is_moved_between_rooms_and_nothing_else_changes(db_session) -> None:
    hall = _hall(db_session)
    wohnen = house_file.upsert_room(db_session, "Wohnen", LIVING, 2600)
    house_file.record_piece(db_session, "hall-bench", "Hall bench", {"style": "oak"}, room_id=hall.id)
    house_file.record_version(db_session, "hall-bench", 1)
    thread = house_file.create_thread(db_session, "Moves")
    house_file.set_thread_room(db_session, thread.id, hall)

    assert house_file.set_piece_room(db_session, "hall-bench", wohnen) is True
    db_session.expire_all()
    from app.db.models import Piece

    piece = db_session.get(Piece, "hall-bench")
    assert piece.room_id == wohnen.id and piece.brief == {"style": "oak"}
    assert house_file.version_row(db_session, "hall-bench", 1) is not None
    assert house_file.thread_scope(db_session, thread.id)[0].name == "Hall"
    assert house_file.set_piece_room(db_session, "hall-bench", None) is True
    assert house_file.set_piece_room(db_session, "unknown", wohnen) is False


def test_a_request_without_a_piece_carries_its_conversation_and_outlives_it(db_session) -> None:
    mine = house_file.create_thread(db_session, "Mine")
    other = house_file.create_thread(db_session, "Other")
    house_file.record_extension_request(db_session, "bevel_mm", "a bevel", thread_id=mine.id)
    house_file.record_extension_request(db_session, "inlay", "an inlay", package_id="hall-bench")
    house_file.record_extension_request(db_session, "old_field", "an old one")

    def fields(**scope):
        return sorted(r.field for r in house_file.open_extension_requests(db_session, **scope))

    assert "bevel_mm" in fields(package_ids=[], thread_id=mine.id)
    assert "bevel_mm" not in fields(package_ids=[], thread_id=other.id)
    assert fields(package_ids=["hall-bench"], thread_id=other.id) == ["inlay"]
    assert fields(package_ids=[], thread_id=None) == []
    assert "old_field" not in fields(package_ids=["hall-bench"], thread_id=mine.id)
    assert "old_field" in [r.field for r in house_file.open_extension_requests(db_session)]

    mine_id = mine.id
    db_session.expunge_all()
    house_file.delete_thread(db_session, mine_id)
    db_session.expire_all()
    kept = [r for r in house_file.open_extension_requests(db_session) if r.field == "bevel_mm"]
    assert len(kept) == 1 and kept[0].thread_id is None


# --- the Rooms page (rooms-page) -----------------------------------------------------------


def _composed(db_session, render_root: Path, room: str, *, status: str = "succeeded", renders=None) -> None:
    from app.blender import storage

    composition = house_file.record_composition(db_session, "room", room)
    house_file.record_composition_version(db_session, composition, 1, None, [])
    folder = storage.composition_version_dir(render_root, composition.slug, 1)
    folder.mkdir(parents=True)
    (folder / "input.json").write_text("{}", encoding="utf-8")
    storage.write_status(folder, status=status, **({"renders": renders} if renders else {}))


def test_rooms_are_listed_with_their_details(db_session, render_root: Path) -> None:
    hall = house_file.upsert_room(db_session, "Hall", [[0, 0], [3000, 0], [3000, 2000], [0, 2000]], 2500)
    house_file.upsert_room(db_session, "L-room", [[0, 0], [4000, 0], [4000, 2000], [2000, 2000], [2000, 4000], [0, 4000]], 2600)
    house_file.record_piece(db_session, "hall-bench", "Hall bench", room_id=hall.id)
    thread = house_file.create_thread(db_session, "Hall")
    house_file.set_thread_room(db_session, thread.id, hall)
    _composed(db_session, render_root, "Hall")

    listed = {r["name"]: r for r in house_file.room_summaries(db_session, render_root)}
    assert listed["Hall"] == {
        "name": "Hall", "width_mm": 3000, "depth_mm": 2000, "corners": 4, "height_mm": 2500, "openings": 0,
        "apartment": None, "pieces": [{"package_id": "hall-bench", "name": "Hall bench"}],
        "conversations": 1, "composition": {"slug": "hall", "versions": [1]},
    }
    assert listed["L-room"]["corners"] == 6 and listed["L-room"]["composition"] is None


def test_deleting_a_room_unassigns_its_pieces_clears_conversations_and_removes_its_composition(
    db_session, render_root: Path
) -> None:
    from app.blender import storage
    from app.db.models import Piece

    hall = house_file.upsert_room(db_session, "Hall", LIVING, 2600)
    house_file.upsert_room(db_session, "Wohnen", LIVING, 2600)
    house_file.record_piece(db_session, "hall-bench", "Hall bench", room_id=hall.id)
    house_file.record_version(db_session, "hall-bench", 1)
    thread = house_file.create_thread(db_session, "Hall")
    house_file.set_thread_room(db_session, thread.id, hall)
    _composed(db_session, render_root, "Hall")
    _composed(db_session, render_root, "Wohnen")
    db_session.commit()
    try:
        assert house_file.delete_room(db_session, render_root, "Hall") is True
        db_session.expire_all()
        assert house_file.room_by_name(db_session, "Hall") is None
        assert db_session.get(Piece, "hall-bench").room_id is None
        assert house_file.version_row(db_session, "hall-bench", 1) is not None
        assert house_file.thread_scope(db_session, thread.id) == (None, None)
        assert house_file.composition_by_scope(db_session, "room", "Hall") is None
        assert not storage.composition_dir(render_root, "hall").exists()
        assert not list((render_root / storage.ROOMS_DIRNAME).glob(".deleted-*"))
        # Other compositions are kept.
        assert house_file.composition_by_scope(db_session, "room", "Wohnen") is not None
        assert storage.list_compositions(render_root) == [("wohnen", [1])]
        assert house_file.delete_room(db_session, render_root, "Hall") is False
    finally:
        from tests.conftest import clean_house_file

        db_session.rollback()
        clean_house_file(db_session.get_bind())


def test_a_room_in_an_apartment_is_refused(db_session, render_root: Path) -> None:
    from app.db.models import Apartment

    flat = Apartment(name="Wohnung", ceiling_height_mm=2600, wall_thickness_mm=100)
    db_session.add(flat)
    db_session.flush()
    house_file.upsert_room(db_session, "Küche", LIVING, 2600, apartment_id=flat.id)
    with pytest.raises(HouseFileError, match="Küche belongs to the apartment Wohnung"):
        house_file.delete_room(db_session, render_root, "Küche")


@pytest.mark.parametrize(
    ("status", "renders"),
    [("running", None), ("succeeded", {"still": {"status": "queued", "tier": "draft"}})],
)
def test_a_room_whose_composition_is_busy_is_refused(db_session, render_root: Path, status, renders) -> None:
    from app.blender import storage

    house_file.upsert_room(db_session, "Hall", LIVING, 2600)
    _composed(db_session, render_root, "Hall", status=status, renders=renders)
    with pytest.raises(HouseFileError, match="building or rendering"):
        house_file.delete_room(db_session, render_root, "Hall")
    assert storage.composition_dir(render_root, "hall").is_dir()


def test_a_failed_commit_leaves_the_folder_and_the_rows(db_session, render_root: Path, monkeypatch) -> None:
    from app.blender import storage

    house_file.upsert_room(db_session, "Hall", LIVING, 2600)
    _composed(db_session, render_root, "Hall")
    db_session.commit()
    try:
        def broken() -> None:
            raise RuntimeError("database went away")

        monkeypatch.setattr(db_session, "commit", broken)
        with pytest.raises(RuntimeError):
            house_file.delete_room(db_session, render_root, "Hall")
        monkeypatch.undo()
        db_session.expire_all()
        assert house_file.room_by_name(db_session, "Hall") is not None
        assert house_file.composition_by_scope(db_session, "room", "Hall") is not None
        assert storage.list_compositions(render_root) == [("hall", [1])]
    finally:
        from tests.conftest import clean_house_file

        db_session.rollback()
        clean_house_file(db_session.get_bind())


def test_notices_are_listed_by_position_then_time_and_a_missing_thread_is_a_no_op(db_session) -> None:
    thread = house_file.create_thread(db_session, "renders")
    later = house_file.add_notice(db_session, thread.id, after_messages=4, outcome="succeeded", tier="draft", text="b")
    first = house_file.add_notice(db_session, thread.id, after_messages=2, outcome="failed", tier="final", text="a")
    same = house_file.add_notice(
        db_session, thread.id, after_messages=4, outcome="succeeded", tier="final", text="c", package_id="hall-bench", version=2
    )
    assert [n.id for n in house_file.notices_for(db_session, thread.id)] == [first.id, later.id, same.id]

    gone = house_file.create_thread(db_session, "gone")
    house_file.delete_thread(db_session, gone.id)
    from uuid import uuid4

    assert house_file.add_notice(db_session, gone.id, after_messages=0, outcome="failed", tier="draft", text="x") is None
    assert house_file.add_notice(db_session, uuid4(), after_messages=0, outcome="failed", tier="draft", text="x") is None
    assert house_file.notices_for(db_session, gone.id) == []


# --- a plan read again replaces the apartment (app-check-2026-10-09) --------------------

WOHNEN = {"name": "Wohnen", "corners_mm": [[0, 0], [5200, 0], [5200, 4000], [0, 4000]]}
KUECHE = {"name": "Küche", "corners_mm": [[5200, 0], [8000, 0], [8000, 4000], [5200, 4000]]}
BAD = {"name": "Bad", "corners_mm": [[0, 4000], [2500, 4000], [2500, 6000], [0, 6000]]}


def _wohnung(db_session) -> None:
    house_file.upsert_apartment(db_session, "Wohnung", 2600, 100, [WOHNEN, KUECHE, BAD])


def test_a_room_written_without_its_apartment_keeps_it(db_session) -> None:
    _wohnung(db_session)
    flat = house_file.apartment_by_name(db_session, "Wohnung")
    house_file.upsert_room(db_session, "Küche", KUECHE["corners_mm"], 2450)
    kitchen = house_file.room_by_name(db_session, "Küche")
    assert kitchen.height_mm == 2450 and kitchen.apartment_id == flat.id


def test_a_replacing_read_lists_kept_new_and_removed_rooms(db_session, render_root: Path) -> None:
    _wohnung(db_session)
    bad = house_file.room_by_name(db_session, "Bad")
    house_file.record_piece(db_session, "towel-rack", "Towel rack", room_id=bad.id)
    narrower = {**WOHNEN, "corners_mm": [[0, 0], [5100, 0], [5100, 4000], [0, 4000]]}
    flur = {"name": "Flur", "corners_mm": [[5200, 4000], [8000, 4000], [8000, 5000], [5200, 5000]]}
    plan = house_file.apartment_replacement(db_session, render_root, "Wohnung", [narrower, KUECHE, flur])
    assert plan["apartment"] == "Wohnung"
    assert {"name": "Wohnen", "stored": [5200, 4000], "read": [5100, 4000]} in plan["rooms"]
    assert plan["new"] == ["Flur"]
    assert plan["removed"] == [{"name": "Bad", "pieces": ["towel-rack"], "composition": None}]
    assert house_file.apartment_replacement(db_session, render_root, "Elsewhere", [WOHNEN]) is None


def test_replacing_deletes_removed_rooms_and_unassigns_their_pieces(db_session, render_root: Path) -> None:
    from app.blender import storage
    from app.db.models import Piece

    _wohnung(db_session)
    bad = house_file.room_by_name(db_session, "Bad")
    house_file.record_piece(db_session, "towel-rack", "Towel rack", room_id=bad.id)
    thread = house_file.create_thread(db_session, "Bad")
    house_file.set_thread_room(db_session, thread.id, bad)
    _composed(db_session, render_root, "Bad")
    db_session.commit()
    try:
        narrower = {**WOHNEN, "corners_mm": [[0, 0], [5100, 0], [5100, 4000], [0, 4000]]}
        flat = house_file.upsert_apartment(
            db_session, "Wohnung", 2600, 100, [narrower, KUECHE], replace=True, render_root=render_root
        )
        db_session.expire_all()
        assert [r.name for r in house_file.rooms_of(db_session, flat)] == ["Küche", "Wohnen"]
        assert house_file.room_by_name(db_session, "Wohnen").corners_mm[1] == [5100, 0]
        assert house_file.room_by_name(db_session, "Bad") is None
        assert db_session.get(Piece, "towel-rack").room_id is None
        assert house_file.thread_scope(db_session, thread.id) == (None, None)
        assert house_file.composition_by_scope(db_session, "room", "Bad") is None
        assert not storage.composition_dir(render_root, "bad").exists()
    finally:
        from tests.conftest import clean_house_file

        db_session.rollback()
        clean_house_file(db_session.get_bind())


def test_replacing_checks_overlap_among_the_read_rooms_only(db_session, render_root: Path) -> None:
    _wohnung(db_session)
    db_session.commit()
    try:
        # The new room covers where `Bad` was; `Bad` is not in the read, so it does not clash.
        bigger = {"name": "Bad neu", "corners_mm": [[0, 4000], [3000, 4000], [3000, 6000], [0, 6000]]}
        house_file.upsert_apartment(
            db_session, "Wohnung", 2600, 100, [WOHNEN, KUECHE, bigger], replace=True, render_root=render_root
        )
        db_session.expire_all()
        assert house_file.room_by_name(db_session, "Bad") is None
        assert house_file.room_by_name(db_session, "Bad neu") is not None
    finally:
        from tests.conftest import clean_house_file

        db_session.rollback()
        clean_house_file(db_session.get_bind())


def test_replacing_is_refused_while_a_removed_rooms_composition_builds(db_session, render_root: Path) -> None:
    from app.blender import storage

    _wohnung(db_session)
    _composed(db_session, render_root, "Bad", status="running")
    with pytest.raises(HouseFileError, match="Bad is building or rendering; read the plan again"):
        house_file.upsert_apartment(
            db_session, "Wohnung", 2600, 100, [WOHNEN, KUECHE], replace=True, render_root=render_root
        )
    assert house_file.room_by_name(db_session, "Bad") is not None
    assert storage.composition_dir(render_root, "bad").is_dir()
