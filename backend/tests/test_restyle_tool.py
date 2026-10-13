"""restyle-variants: the Builder's `restyle_render` tool, with fake launchers (no Blender)."""

from __future__ import annotations

import json
import time
from dataclasses import replace

from app.blender import storage
from app.restyle import store
from plugins.restyle_render.tool import preview as restyle_preview
from plugins.restyle_render.tool import run as restyle_run
from tests.test_builder_tools import composed, folder_of, made


def slot_of(tool_state) -> str:
    spec = json.loads((folder_of(tool_state) / storage.INPUT_FILE).read_text(encoding="utf-8"))
    return next(iter(spec["materials"]))


def wait_variants(folder, count: int, seconds: float = 10.0) -> list[dict]:
    deadline = time.monotonic() + seconds
    found: list[dict] = []
    while time.monotonic() < deadline:
        found = store.list_variants(folder)
        if len(found) >= count:
            return found
        time.sleep(0.05)
    raise AssertionError(f"only {len(found)} variants appeared")


def test_two_looks_start_one_batch_with_one_estimate_and_publish_two_stills(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    slot = slot_of(tool_state)
    args = {"package_id": "bench", "tier": "draft", "slots": [slot], "looks": ["walnut", "oak"]}
    assert restyle_preview(args, make_ctx()) is None
    result = restyle_run(args, make_ctx())
    assert result.startswith("Started 2 draft restyle stills of bench version 1 (Walnut, Natural oak): about")
    assert "appearance only, not a priced material" in result and "design itself is unchanged" in result
    found = wait_variants(folder_of(tool_state), 2)
    assert {item["tier"] for item in found} == {"draft"} and {item["source"] for item in found} == {"restyle"}
    assert (folder_of(tool_state) / "spec.json").is_file()


def test_all_expands_to_every_look(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    result = restyle_run(
        {"package_id": "bench", "tier": "draft", "slots": [slot_of(tool_state)], "looks": ["all"]}, make_ctx()
    )
    assert result.startswith("Started 6 draft restyle stills")
    wait_variants(folder_of(tool_state), 6)


def test_a_missing_tier_is_refused_and_nothing_launches(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    launched = len(tool_state.launched)
    result = restyle_run({"package_id": "bench", "slots": [slot_of(tool_state)], "looks": ["walnut"]}, make_ctx())
    assert "a tier is required" in result
    assert len(tool_state.launched) == launched


def test_final_is_refused_even_with_approval(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    launched = len(tool_state.launched)
    args = {"package_id": "bench", "tier": "final", "slots": [slot_of(tool_state)], "looks": ["walnut"]}
    assert "concept picture" in restyle_preview(args, make_ctx())
    assert "concept picture" in restyle_run(args, replace(make_ctx(), approved=True))
    assert len(tool_state.launched) == launched


def test_raw_resolution_and_unknown_fields_are_refused_by_name(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    base = {"package_id": "bench", "tier": "draft", "slots": [slot_of(tool_state)], "looks": ["walnut"]}
    assert "resolution cannot be set" in restyle_run({**base, "resolution": 4000}, make_ctx())
    assert "thickness_mm" in restyle_run({**base, "thickness_mm": 20}, make_ctx())


def test_an_unknown_slot_names_it(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    result = restyle_run({"package_id": "bench", "tier": "draft", "slots": ["legs"], "looks": ["walnut"]}, make_ctx())
    assert "legs" in result and slot_of(tool_state) in result


def test_an_unbuilt_version_cannot_be_restyled(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state, wait=False)
    folder = folder_of(tool_state)
    storage.write_status(folder, status="queued")
    result = restyle_run({"package_id": "bench", "tier": "draft", "slots": ["carcass"], "looks": ["walnut"]}, make_ctx())
    assert "not built yet" in result


def test_a_piece_takes_looks_and_a_room_takes_styles(make_ctx, tool_deps, tool_state) -> None:
    made(make_ctx, tool_state)
    assert "takes looks, not styles" in restyle_run(
        {"package_id": "bench", "tier": "draft", "styles": ["scandi"]}, make_ctx()
    )
    composed(make_ctx, tool_deps, tool_state)
    assert "takes styles, not looks" in restyle_run(
        {"composition": "Wohnen", "tier": "draft", "looks": ["walnut"]}, make_ctx()
    )
    assert "exactly one target" in restyle_run(
        {"composition": "Wohnen", "package_id": "bench", "tier": "draft", "styles": ["scandi"]}, make_ctx()
    )


def test_a_composed_room_restyles_with_styles(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    result = restyle_run({"composition": "Wohnen", "tier": "preview", "styles": ["japandi", "industrial"]}, make_ctx())
    assert result.startswith("Started 2 preview restyle stills of wohnen version 1 (Japandi, Industrial)")
    folder = storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1)
    found = wait_variants(folder, 2)
    assert {item["tier"] for item in found} == {"preview"}


def test_a_full_version_says_the_oldest_will_be_replaced(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    folder = folder_of(tool_state)
    for index in range(store.MAX_VARIANTS):
        target = store.variants_dir(folder) / f"old-{index:02d}"
        target.mkdir(parents=True)
        (target / "still.png").write_bytes(b"x")
        (target / "scene.json").write_text(json.dumps({"created_at": f"2026-01-{index + 1:02d}"}), encoding="utf-8")
    result = restyle_run(
        {"package_id": "bench", "tier": "draft", "slots": [slot_of(tool_state)], "looks": ["walnut"]}, make_ctx()
    )
    assert "the oldest 1 will be replaced" in result


def test_a_restyle_changes_no_spec_and_makes_no_new_version(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    folder = folder_of(tool_state)
    before = {name: (folder / name).read_bytes() for name in ("input.json", "spec.json", "model.blend")}
    versions = storage.versions(tool_state.settings.render_root, "bench")
    restyle_run(
        {"package_id": "bench", "tier": "draft", "slots": [slot_of(tool_state)], "looks": ["walnut"]}, make_ctx()
    )
    wait_variants(folder, 1)
    assert {name: (folder / name).read_bytes() for name in before} == before
    assert storage.versions(tool_state.settings.render_root, "bench") == versions
