"""render-review: evidence selection per render kind; migration 0005."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.review import ReviewRefused, collect, direction_name, review_schema
from app.db.models import Base
from app.db.session import make_engine
from conftest import BACKEND_ROOT

# 1×1 PNG, enough for collect() to treat the file as present.
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)

DESK = {
    "kind": "custom_build",
    "schema_version": 1,
    "units": "mm",
    "name": "Hall bench",
    "materials": {"carcass": {"material": "18 mm oak", "thickness_mm": 18}},
    "modules": [
        {
            "id": "cabinet",
            "name": "Cabinet",
            "x": 0,
            "y": 0,
            "z": 0,
            "width": 1000,
            "height": 700,
            "depth": 300,
            "carcass": "carcass",
            "shelves": 2,
            "fronts": [{"type": "drawer"}, {"type": "drawer"}],
        }
    ],
}


def _png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PIXEL)


def _version(root: Path, package_id: str = "hall-bench", version: int = 1) -> Path:
    folder = root / package_id / f"v{version}"
    folder.mkdir(parents=True)
    (folder / "input.json").write_text(json.dumps(DESK), encoding="utf-8")
    return folder


def test_a_12_frame_draft_turntable_gives_frames_0_3_6_9(tmp_path: Path) -> None:
    folder = _version(tmp_path)
    _png(folder / "screenshot.png")
    for index in range(12):
        _png(folder / "frames" / f"frame_{index:03d}.png")

    evidence = collect(tmp_path, "hall-bench", 1)

    labels = [image.label for image in evidence.images]
    assert labels[0] == "iso"
    assert labels[1:] == [f"turntable view {k}" for k in (1, 2, 3, 4)]
    assert "Overall: 1000 × 700 × 300 mm" in evidence.facts
    assert "2 drawer" in evidence.facts
    assert evidence.renders[0] == "screenshot.png"
    assert evidence.renders[1] == "frames/frame_000.png"


def test_the_straight_on_views_follow_the_screenshot(tmp_path: Path) -> None:
    folder = _version(tmp_path)
    for name in ("screenshot.png", "front.png", "side.png", "top.png"):
        _png(folder / name)
    for index in range(12):
        _png(folder / "frames" / f"frame_{index:03d}.png")

    evidence = collect(tmp_path, "hall-bench", 1)

    assert [image.label for image in evidence.images] == [
        "iso",
        "front",
        "side",
        "top",
        "turntable view 1",
        "turntable view 2",
        "turntable view 3",
        "turntable view 4",
    ]
    assert evidence.images[1].description == "shows width and height"
    assert evidence.renders[1:4] == ["front.png", "side.png", "top.png"]


def test_a_still_only_version_sends_the_still(tmp_path: Path) -> None:
    folder = _version(tmp_path)
    _png(folder / "screenshot.png")
    _png(folder / "still.png")

    evidence = collect(tmp_path, "hall-bench", 1)

    assert [image.label for image in evidence.images] == ["iso", "still"]


def test_a_room_still_is_added(tmp_path: Path) -> None:
    folder = _version(tmp_path)
    _png(folder / "screenshot.png")
    _png(folder / "still.png")
    _png(folder / "room" / "still.png")

    evidence = collect(tmp_path, "hall-bench", 1)

    assert [image.label for image in evidence.images] == ["iso", "still", "room"]
    assert "room/still.png" in evidence.renders


def test_a_screenshot_only_version_is_enough(tmp_path: Path) -> None:
    folder = _version(tmp_path)
    _png(folder / "screenshot.png")

    evidence = collect(tmp_path, "hall-bench", 1)

    assert [image.label for image in evidence.images] == ["iso"]


def test_room_frames_are_labelled_room_and_room_opposite_side(tmp_path: Path) -> None:
    folder = _version(tmp_path)
    _png(folder / "screenshot.png")
    for index in range(12):
        _png(folder / "room" / "frames" / f"frame_{index:03d}.png")

    labels = [image.label for image in collect(tmp_path, "hall-bench", 1).images]

    assert labels == ["iso", "room", "room opposite side"]


def test_no_label_holds_a_frame_or_image_number(tmp_path: Path) -> None:
    folder = _version(tmp_path)
    for name in ("screenshot.png", "front.png", "side.png", "top.png"):
        _png(folder / name)
    for index in range(12):
        _png(folder / "frames" / f"frame_{index:03d}.png")
    _write_turntable(folder, [0, 3, 6, 9])

    for image in collect(tmp_path, "hall-bench", 1).images:
        assert "frame" not in image.label and "image" not in image.label
        assert "exploded" not in image.label


def _write_turntable(folder: Path, indexes: list[int]) -> None:
    # Cameras on a 12-step orbit starting at CAM_Iso's angle, counter-clockwise from above.
    start = math.atan2(-4.5, 3.2)
    cameras = [
        {
            "index": index,
            "location_mm": [
                round(5000 * math.cos(start + 2 * math.pi * index / 12), 1),
                round(5000 * math.sin(start + 2 * math.pi * index / 12), 1),
                1500,
            ],
        }
        for index in indexes
    ]
    record = {"kind": "turntable", "target_mm": [0, 0, 350], "cameras": cameras}
    (folder / "scene.json").write_text(json.dumps({"turntable": record}), encoding="utf-8")


@pytest.mark.parametrize(
    ("location", "name"),
    [
        ((1000, 0), "right side"),
        ((0, -1000), "front"),
        ((1000, -1000), "front-right"),
        ((0, 1000), "back"),
        ((-1000, 0), "left side"),
    ],
)
def test_direction_names_follow_the_front_at_minus_y(location, name) -> None:
    assert direction_name([*location, 1500], [0, 0, 350]) == name


def test_recorded_cameras_give_four_unique_direction_labels(tmp_path: Path) -> None:
    folder = _version(tmp_path)
    _png(folder / "screenshot.png")
    for index in range(12):
        _png(folder / "frames" / f"frame_{index:03d}.png")
    _write_turntable(folder, list(range(12)))

    labels = [image.label for image in collect(tmp_path, "hall-bench", 1).images][1:]

    assert labels == [
        "turntable front-right",
        "turntable back-right",
        "turntable back-left",
        "turntable front-left",
    ]
    assert len(set(labels)) == 4


def test_a_repeated_direction_gets_a_2(tmp_path: Path) -> None:
    folder = _version(tmp_path)
    _png(folder / "screenshot.png")
    for index in range(2):
        _png(folder / "frames" / f"frame_{index:03d}.png")
    record = {"target_mm": [0, 0, 0], "cameras": [
        {"index": 0, "location_mm": [0, -900, 0]}, {"index": 1, "location_mm": [10, -900, 0]}]}
    (folder / "scene.json").write_text(json.dumps({"turntable": record}), encoding="utf-8")

    labels = [image.label for image in collect(tmp_path, "hall-bench", 1).images][1:]

    assert labels == ["turntable front", "turntable front 2"]


def test_the_schema_refuses_a_view_that_was_not_sent() -> None:
    schema = review_schema(["iso", "front"])
    item = {"aspect": "brief", "expected": "a", "expected_source": "brief",
            "observed": "b", "view": "iso", "severity": "minor"}
    assert schema.model_validate({"items": [item]})
    with pytest.raises(ValueError):
        schema.model_validate({"items": [{**item, "view": "turntable back"}]})


def test_an_unbuilt_version_is_refused(tmp_path: Path) -> None:
    _version(tmp_path)
    with pytest.raises(ReviewRefused, match="build or render"):
        collect(tmp_path, "hall-bench", 1)


def test_upgrade_and_downgrade_leave_no_drift(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", migrated_database)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.downgrade(config, "0006_plugins_budgets")
    engine = make_engine(migrated_database)
    try:
        with Session(engine) as session:
            tables = set(
                session.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                ).scalars()
            )
        assert "reviews" not in tables
        assert "review_items" not in tables
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = make_engine(migrated_database)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={"compare_type": True},
            )
            diff = compare_metadata(context, Base.metadata)
        app_diff = [
            item
            for item in diff
            if "review_items" in repr(item)
            or "Table('reviews'" in repr(item)
            or "table=<reviews>" in repr(item)
        ]
    finally:
        engine.dispose()
    assert app_diff == [], f"schema drift after upgrade/downgrade: {app_diff!r}"
