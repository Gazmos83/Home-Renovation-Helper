"""piece-size-room-warning: a built version too big for its room is warned about, never refused."""

from __future__ import annotations

import json

from app.agent import house_file, notices
from app.agent.tools.base import ToolDeps
from app.blender import storage
from app.db.models import Room
from tests.graph_helpers import make_harness
from tests.test_notices import built

WOHNEN = [[0, 0], [4000, 0], [4000, 3000], [0, 3000]]


def _room(corners=WOHNEN, height=2500) -> Room:
    return Room(name="Wohnen", corners_mm=corners, height_mm=height)


def test_taller_than_the_ceiling() -> None:
    assert house_file.size_warnings(_room(), {"w": 600, "d": 400, "h": 2600}) == [
        "Too big for Wohnen: 2600 mm tall, the ceiling is 2500 mm."
    ]


def test_wider_than_the_longest_wall() -> None:
    assert house_file.size_warnings(_room(), {"w": 4200, "d": 400, "h": 900}) == [
        "Too big for Wohnen: 4200 mm wide, the longest wall is 4000 mm."
    ]


def test_both() -> None:
    assert len(house_file.size_warnings(_room(), {"w": 4200, "d": 400, "h": 2600})) == 2


def test_fits_within_the_tolerance() -> None:
    assert house_file.size_warnings(_room(), {"w": 4000.5, "d": 400, "h": 2500}) == []


def test_an_l_shaped_rooms_longest_edge_counts() -> None:
    l_shape = [[0, 0], [5000, 0], [5000, 2000], [2000, 2000], [2000, 4000], [0, 4000]]
    assert house_file.size_warnings(_room(l_shape), {"w": 4800, "d": 400, "h": 900}) == []
    assert house_file.size_warnings(_room(l_shape), {"w": 5200, "d": 400, "h": 900}) == [
        "Too big for Wohnen: 5200 mm wide, the longest wall is 5000 mm."
    ]


def _piece_in_wohnen(tool_state, size: dict[str, int], *, room: bool = True) -> None:
    with ToolDeps(tool_state).session() as session:
        house_file.record_piece(session, "hochschrank", "Hochschrank")
        house_file.record_version(session, "hochschrank", 2)
        if room:
            wohnen = house_file.upsert_room(session, "Wohnen", WOHNEN, 2500)
            house_file.set_piece_room(session, "hochschrank", wohnen)
        session.commit()
    folder = storage.version_dir(tool_state.settings.render_root, "hochschrank", 2)
    folder.mkdir(parents=True, exist_ok=True)
    envelope = {"width": size["w"], "height": size["h"], "depth": size["d"]}
    (folder / storage.INPUT_FILE).write_text(json.dumps({"envelope": envelope, "modules": []}), encoding="utf-8")


def _notice(tool_state, size: dict[str, int], *, room: bool = True, outcome: str = "succeeded") -> str:
    harness = make_harness(tool_state)
    tool_state.graph = harness.graph
    harness.turn("hello")
    _piece_in_wohnen(tool_state, size, room=room)
    notices.post_build(ToolDeps(tool_state), harness.thread, "hochschrank", 2, outcome)
    return built(tool_state, harness.thread)[-1][3]


def test_a_build_notice_warns_when_taller_than_the_ceiling(tool_state) -> None:
    assert _notice(tool_state, {"w": 600, "d": 400, "h": 2600}) == (
        "hochschrank version 2 is built. Too big for Wohnen: 2600 mm tall, the ceiling is 2500 mm."
    )


def test_a_build_notice_warns_when_wider_than_the_longest_wall(tool_state) -> None:
    assert _notice(tool_state, {"w": 4200, "d": 400, "h": 900}).endswith(
        "Too big for Wohnen: 4200 mm wide, the longest wall is 4000 mm."
    )


def test_a_build_notice_that_fits_says_built_alone(tool_state) -> None:
    assert _notice(tool_state, {"w": 1200, "d": 400, "h": 900}) == "hochschrank version 2 is built."


def test_a_piece_with_no_room_gets_no_warning(tool_state) -> None:
    assert _notice(tool_state, {"w": 600, "d": 400, "h": 2600}, room=False) == "hochschrank version 2 is built."


def test_a_failed_build_gets_no_warning(tool_state) -> None:
    assert "Too big" not in _notice(tool_state, {"w": 600, "d": 400, "h": 2600}, outcome="failed")
