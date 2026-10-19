"""furniture-packages: a piece version is duplicated into a new piece (duplicate-piece)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.agent import house_file
from app.blender import storage
from app.db.models import Thread
from app.packages import duplicate, service
from tests.api_helpers import desk

INPUTS = {"data_sheets": {"hinge": "frozen"}}


def make_source(state, package_id: str = "sideboard-1200", name: str = "Sideboard", versions: int = 1) -> None:
    root = state.settings.render_root
    with Session(state.engine) as session:
        room = house_file.upsert_room(session, "Hall", [[0, 0], [3000, 0], [3000, 2000], [0, 2000]], 2500)
        house_file.record_piece(session, package_id, name, brief={"room": "Hall"}, room_id=room.id)
        for n in range(1, versions + 1):
            spec = {**desk(), "name": name}
            spec["modules"][0]["width"] = 600 + n * 100
            created = service.create_version(root, package_id, spec, lambda _v: None, inputs={**INPUTS, "n": n})
            house_file.record_version(session, package_id, created["version"])
        session.commit()


def run_duplicate(state, version: int | None = None, name: str = "Sideboard Hall", package_id: str | None = None):
    root = state.settings.render_root
    started: list[tuple] = []
    with Session(state.engine) as session:
        checked = duplicate.plan(session, root, "sideboard-1200", version, name, package_id)
        created = duplicate.create(session, root, checked, lambda thread, v: started.append((thread, v)))
    return created, started


def test_the_latest_version_is_copied_as_version_one_of_a_new_piece(tool_state) -> None:
    make_source(tool_state, versions=3)
    root = tool_state.settings.render_root
    source_before = (storage.version_dir(root, "sideboard-1200", 3) / storage.INPUT_FILE).read_text()
    created, started = run_duplicate(tool_state)
    assert created["package_id"] == "sideboard-hall" and created["version"] == 1
    folder = storage.version_dir(root, "sideboard-hall", 1)
    stored = json.loads((folder / storage.INPUT_FILE).read_text())
    assert stored["name"] == "Sideboard Hall"
    assert stored["modules"][0]["width"] == 900
    assert storage.read_hardware_inputs(folder) == {**INPUTS, "n": 3}
    assert started and started[0][1] == 1
    with Session(tool_state.engine) as session:
        listing = {p["package_id"]: p for p in house_file.pieces(session, root)}
        copy = listing["sideboard-hall"]
        assert copy["name"] == "Sideboard Hall" and copy["brief"] == {"room": "Hall"}
        assert copy["versions"][0]["changes"] == ["duplicated from sideboard-1200 v3"]
        assert house_file.piece_room_names(session)["sideboard-hall"] == "Hall"
        thread = session.get(Thread, started[0][0])
        assert thread.package_id == "sideboard-hall" and str(thread.id) == created["thread_id"]
        assert house_file.thread_id_for_piece(session, "sideboard-1200") is None
    assert storage.versions(root, "sideboard-1200") == [1, 2, 3]
    assert (storage.version_dir(root, "sideboard-1200", 3) / storage.INPUT_FILE).read_text() == source_before


def test_an_earlier_version_is_copied_when_chosen(tool_state) -> None:
    make_source(tool_state, versions=3)
    run_duplicate(tool_state, version=1)
    folder = storage.version_dir(tool_state.settings.render_root, "sideboard-hall", 1)
    assert json.loads((folder / storage.INPUT_FILE).read_text())["modules"][0]["width"] == 700


def test_approval_is_not_copied(tool_state) -> None:
    make_source(tool_state)
    with Session(tool_state.engine) as session:
        house_file.version_row(session, "sideboard-1200", 1).approved_at = datetime.now(UTC)
        session.commit()
    run_duplicate(tool_state)
    with Session(tool_state.engine) as session:
        assert house_file.version_row(session, "sideboard-hall", 1).approved_at is None


def test_a_source_without_frozen_inputs_is_copied_without_them(tool_state) -> None:
    make_source(tool_state)
    folder = storage.version_dir(tool_state.settings.render_root, "sideboard-1200", 1)
    (folder / storage.HARDWARE_INPUTS_FILE).unlink()
    run_duplicate(tool_state)
    copy = storage.version_dir(tool_state.settings.render_root, "sideboard-hall", 1)
    assert storage.read_hardware_inputs(copy) is None


def test_the_default_id_skips_taken_ids(tool_state) -> None:
    make_source(tool_state, package_id="sideboard-copy", name="Old")
    with Session(tool_state.engine) as session:
        assert duplicate.default_id(session, tool_state.settings.render_root, "Sideboard (copy)") == "sideboard-copy-2"


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"package_id": "sideboard-1200"}, "package_exists"),
        ({"name": "sideboard"}, "name_taken"),
        ({"name": "  "}, "invalid_name"),
        ({"version": 9}, "not_found"),
    ],
)
def test_refusals_create_nothing(tool_state, kwargs, code) -> None:
    make_source(tool_state)
    with pytest.raises(duplicate.DuplicateRefused) as refused:
        run_duplicate(tool_state, **kwargs)
    assert refused.value.code == code
    assert [p for p, _ in storage.list_packages(tool_state.settings.render_root)] == ["sideboard-1200"]


def test_a_design_the_schema_now_refuses_is_refused_by_field_name(tool_state) -> None:
    make_source(tool_state)
    path = storage.version_dir(tool_state.settings.render_root, "sideboard-1200", 1) / storage.INPUT_FILE
    document = json.loads(path.read_text())
    document["modules"][0]["bevel_mm"] = 3
    path.write_text(json.dumps(document))
    with pytest.raises(duplicate.DuplicateRefused) as refused:
        run_duplicate(tool_state)
    assert refused.value.code == "invalid_spec" and "bevel_mm" in str(refused.value)
    assert storage.versions(tool_state.settings.render_root, "sideboard-hall") == []


def test_an_unknown_source_is_refused(tool_state) -> None:
    with Session(tool_state.engine) as session, pytest.raises(duplicate.DuplicateRefused) as refused:
        duplicate.plan(session, tool_state.settings.render_root, "nothing-here", None, "X", None)
    assert refused.value.code == "not_found"
