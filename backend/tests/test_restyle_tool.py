"""restyle-variants: the Builder's `restyle_render` tool, with fake launchers (no Blender).

Renders are made of rooms (rooms-only-renders): a composed room is restyled with styles, and
a piece is not restyled.
"""

from __future__ import annotations

import json
import time
from dataclasses import replace

from app.blender import storage
from app.restyle import store
from plugins.restyle_render.tool import preview as restyle_preview
from plugins.restyle_render.tool import run as restyle_run
from tests.test_builder_tools import composed, folder_of, made


def room_folder(tool_state):
    return storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1)


def wait_variants(folder, count: int, seconds: float = 10.0) -> list[dict]:
    deadline = time.monotonic() + seconds
    found: list[dict] = []
    while time.monotonic() < deadline:
        found = store.list_variants(folder)
        if len(found) >= count:
            return found
        time.sleep(0.05)
    raise AssertionError(f"only {len(found)} variants appeared")


STYLED = {"composition": "Wohnen", "tier": "draft", "styles": ["japandi"]}


def test_a_piece_is_not_restyled(make_ctx, tool_state) -> None:
    from plugins.render_turntable.tool import PIECE_REFUSED

    made(make_ctx, tool_state)
    launched = len(tool_state.launched)
    for args in (
        {"package_id": "bench", "tier": "draft", "slots": ["carcass"], "looks": ["walnut"]},
        {"package_id": "bench", "tier": "draft", "styles": ["scandi"]},
        {"composition": "Wohnen", "package_id": "bench", "tier": "draft", "styles": ["scandi"]},
    ):
        assert restyle_preview(args, make_ctx()) == PIECE_REFUSED
        assert restyle_run(args, make_ctx()) == PIECE_REFUSED
    assert len(tool_state.launched) == launched
    assert store.list_variants(folder_of(tool_state)) == []


def test_two_styles_start_one_batch_with_one_estimate_and_publish_two_turntables(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    args = {"composition": "Wohnen", "tier": "draft", "styles": ["japandi", "industrial"]}
    assert restyle_preview(args, make_ctx()) is None
    result = restyle_run(args, make_ctx())
    assert result.startswith("Started 2 draft restyle turntables of wohnen version 1 (Japandi, Industrial): about")
    assert "appearance only, not a priced material" in result and "design itself is unchanged" in result
    found = wait_variants(room_folder(tool_state), 2)
    assert {item["tier"] for item in found} == {"draft"} and {item["source"] for item in found} == {"restyle"}
    for item in found:
        variant = store.variant_dir(room_folder(tool_state), item["id"])
        assert sorted(p.name for p in (variant / "frames").iterdir()) == [f"frame_{i:03d}.png" for i in range(12)]
        assert (variant / "still.png").read_bytes() == (variant / "frames" / "frame_000.png").read_bytes()


def test_a_missing_tier_is_refused_and_nothing_launches(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    launched = len(tool_state.launched)
    assert "a tier is required" in restyle_run({"composition": "Wohnen", "styles": ["japandi"]}, make_ctx())
    assert len(tool_state.launched) == launched


def test_final_is_refused_even_with_approval(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    launched = len(tool_state.launched)
    args = {**STYLED, "tier": "final"}
    assert "concept picture" in restyle_preview(args, make_ctx())
    assert "concept picture" in restyle_run(args, replace(make_ctx(), approved=True))
    assert len(tool_state.launched) == launched


def test_raw_resolution_and_unknown_fields_are_refused_by_name(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    assert "resolution cannot be set" in restyle_run({**STYLED, "resolution": 4000}, make_ctx())
    assert "thickness_mm" in restyle_run({**STYLED, "thickness_mm": 20}, make_ctx())


def test_a_room_takes_styles_not_looks(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    assert "takes styles, not looks" in restyle_run(
        {"composition": "Wohnen", "tier": "draft", "looks": ["walnut"]}, make_ctx()
    )
    assert "name the composed room" in restyle_run({"tier": "draft", "styles": ["japandi"]}, make_ctx())


def test_a_restyle_at_preview_is_refused_as_an_unknown_tier(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    launched = len(tool_state.launched)
    result = restyle_run({**STYLED, "tier": "preview"}, make_ctx())
    assert "preview" in result and "the tiers are draft, final" in result
    assert len(tool_state.launched) == launched


def test_a_full_version_says_the_oldest_will_be_replaced(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    folder = room_folder(tool_state)
    for index in range(store.MAX_VARIANTS):
        target = store.variants_dir(folder) / f"old-{index:02d}"
        target.mkdir(parents=True)
        (target / "still.png").write_bytes(b"x")
        (target / "scene.json").write_text(json.dumps({"created_at": f"2026-01-{index + 1:02d}"}), encoding="utf-8")
    assert "the oldest 1 will be replaced" in restyle_run(STYLED, make_ctx())


def test_a_restyle_changes_no_document_and_makes_no_new_version(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    folder = room_folder(tool_state)
    before = {name: (folder / name).read_bytes() for name in (storage.INPUT_FILE, "model.blend")}
    versions = storage.composition_versions(tool_state.settings.render_root, "wohnen")
    restyle_run(STYLED, make_ctx())
    wait_variants(folder, 1)
    assert {name: (folder / name).read_bytes() for name in before} == before
    assert storage.composition_versions(tool_state.settings.render_root, "wohnen") == versions


def test_a_composition_restyle_records_no_run(make_ctx, tool_deps, tool_state) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.db.models import RenderRun

    composed(make_ctx, tool_deps, tool_state)
    restyle_run(STYLED, make_ctx(slot="builder"))
    wait_variants(room_folder(tool_state), 1)
    with Session(tool_state.engine) as session:
        assert list(session.scalars(select(RenderRun).where(RenderRun.package_id == "wohnen"))) == []
