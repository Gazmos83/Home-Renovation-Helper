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
