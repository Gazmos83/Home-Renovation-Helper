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


def test_a_room_outline_that_is_not_convex_is_refused(db_session) -> None:
    with pytest.raises(HouseFileError, match="convex"):
        house_file.validate_room(
            "L", [[0, 0], [4000, 0], [4000, 2000], [2000, 2000], [2000, 4000], [0, 4000]], 2600
        )


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
