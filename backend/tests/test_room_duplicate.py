"""duplicate-room: a measured room copied under a new name, with at most one layout version."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app import compositions, rooms_duplicate
from app.agent import house_file
from app.blender import storage
from plugins.compose_room.tool import run as compose_run
from tests import test_compose_room as compose
from tests.conftest import wait_for_status

DESK, SOFA, WOHNEN = compose.DESK, compose.SOFA, compose.WOHNEN
# The composition tests' fixtures: the measured room, and an approved built desk in it.
room, approved_desk = compose.room, compose.approved_desk

FLOOR = {"tile_width_mm": 600, "tile_length_mm": 600, "tile_colour": "#e8e4dc", "grout_colour": "#9a958c", "grout_width_mm": 3}


def _duplicate(tool_deps, name: str, version: int | None, started: list | None = None):
    with tool_deps.session() as session:
        checked = rooms_duplicate.plan(
            session, tool_deps.render_root, "Wohnen", name, version,
            max_items=30, rules=tool_deps.design_rules, lighting=tool_deps.lighting,
        )
        return rooms_duplicate.create(
            session, tool_deps.render_root, checked, lambda slug, n: (started if started is not None else []).append((slug, n))
        )


def _layout(make_ctx, tool_state, items, floor=None) -> None:
    arguments = {"room": "Wohnen", "items": items, **({"floor": floor} if floor else {})}
    compose_run(arguments, replace(make_ctx(), approved=True))
    root = tool_state.settings.render_root
    wait_for_status(storage.composition_version_dir(root, "wohnen", storage.composition_versions(root, "wohnen")[-1]))


def _room_names(tool_deps) -> list[str]:
    with tool_deps.session() as session:
        return [r.name for r in house_file.rooms(session)]


def test_a_room_only_copy_has_the_measurements_and_no_layout(tool_deps, room) -> None:
    with tool_deps.session() as session:
        source = house_file.room_by_name(session, "Wohnen")
        source.notes = "south light"
        session.commit()
    assert _duplicate(tool_deps, "Wohnen (copy)", None) == {"room": "Wohnen (copy)", "composition": None}
    with tool_deps.session() as session:
        source, copy = house_file.room_by_name(session, "Wohnen"), house_file.room_by_name(session, "Wohnen (copy)")
        assert (copy.corners_mm, copy.height_mm, copy.wall_thickness_mm, copy.openings, copy.notes) == (
            source.corners_mm, source.height_mm, source.wall_thickness_mm, source.openings, "south light"
        )
        assert copy.apartment_id is None
        assert house_file.composition_by_scope(session, "room", "Wohnen (copy)") is None


def test_the_chosen_layout_becomes_version_one_and_builds(make_ctx, tool_deps, tool_state, approved_desk) -> None:
    _layout(make_ctx, tool_state, [SOFA])
    _layout(make_ctx, tool_state, [DESK, SOFA], FLOOR)
    started: list = []
    created = _duplicate(tool_deps, "Wohnen B", 2, started)
    assert created == {"room": "Wohnen B", "composition": {"slug": "wohnen-b", "version": 1}}
    assert started == [("wohnen-b", 1)]
    root = tool_state.settings.render_root
    source = compositions.read_document(storage.composition_version_dir(root, "wohnen", 2))
    copy = compositions.read_document(storage.composition_version_dir(root, "wohnen-b", 1))
    assert copy["items"] == source["items"] and copy["floor"] == source["floor"]
    assert copy["scope"] == {"room": "Wohnen B"}
    with tool_deps.session() as session:
        rows = house_file.composition_version_rows(
            session, house_file.composition_by_scope(session, "room", "Wohnen B")
        )
        assert [(r.version, r.changes) for r in rows] == [(1, ["duplicated from Wohnen v2"])]
        # The source is unchanged.
        assert [r.version for r in house_file.composition_version_rows(
            session, house_file.composition_by_scope(session, "room", "Wohnen")
        )] == [1, 2]


def test_a_layout_with_an_unapproved_piece_is_refused_and_writes_nothing(make_ctx, tool_deps, tool_state, approved_desk) -> None:
    _layout(make_ctx, tool_state, [DESK])
    with tool_deps.session() as session:
        house_file.unapprove_version(session, "desk", 1)
        session.commit()
    with pytest.raises(rooms_duplicate.RoomDuplicateRefused) as refused:
        _duplicate(tool_deps, "Wohnen B", 1)
    assert refused.value.code == "layout_refused" and "desk version 1 is not approved" in str(refused.value)
    assert _room_names(tool_deps) == ["Wohnen"]
    assert not storage.composition_dir(tool_state.settings.render_root, "wohnen-b").exists()


@pytest.mark.parametrize(
    ("name", "version", "code"),
    [("wohnen", None, "name_taken"), ("  ", None, "invalid_name"), ("Wohnen B", 3, "not_found")],
)
def test_a_refused_duplicate_writes_nothing(tool_deps, room, name, version, code) -> None:
    with pytest.raises(rooms_duplicate.RoomDuplicateRefused) as refused:
        _duplicate(tool_deps, name, version)
    assert refused.value.code == code
    assert _room_names(tool_deps) == ["Wohnen"]


def test_an_unknown_room_is_not_found(tool_deps) -> None:
    with tool_deps.session() as session, pytest.raises(rooms_duplicate.RoomDuplicateRefused) as refused:
        rooms_duplicate.plan(session, tool_deps.render_root, "Nowhere", "B", None, max_items=30, rules=(), lighting=tool_deps.lighting)
    assert refused.value.code == "not_found"


def test_a_room_of_an_apartment_is_copied_standalone(tool_deps) -> None:
    with tool_deps.session() as session:
        house_file.upsert_apartment(
            session, "Wohnung", 2600, 100, [{"name": "Wohnen", "corners_mm": WOHNEN, "height_mm": None, "openings": []}]
        )
        session.commit()
    _duplicate(tool_deps, "Wohnen B", None)
    with tool_deps.session() as session:
        assert house_file.room_by_name(session, "Wohnen B").apartment_id is None
        assert house_file.room_by_name(session, "Wohnen").apartment_id is not None
