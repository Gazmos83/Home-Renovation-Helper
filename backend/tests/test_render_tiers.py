"""render-guard: tiers come from configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.render.tiers import TierError, load_tiers

GOOD = """
tiers:
  draft: {frames: 12, resolution: 800, engine: eevee, timeout_multiplier: 1}
  final: {frames: 36, resolution: 1500, engine: cycles, timeout_multiplier: 24}
"""


def _load(tmp_path: Path, text: str):
    path = tmp_path / "render.yaml"
    path.write_text(text, encoding="utf-8")
    return load_tiers(path)


def test_the_shipped_tiers_load() -> None:
    tiers = load_tiers()
    draft, final = (tiers.get(n) for n in ("draft", "final"))
    assert (draft.frames, draft.resolution, draft.engine) == (12, 800, "eevee")
    assert (final.frames, final.resolution, final.engine) == (36, 1500, "cycles")
    assert (draft.timeout_multiplier, final.timeout_multiplier) == (1, 36)
    assert [name for name, _ in tiers.items()] == ["draft", "final"]
    assert final.blender_engine == "CYCLES"
    assert draft.blender_engine == "BLENDER_EEVEE"


def test_megapixels() -> None:
    tiers = load_tiers()
    assert tiers.get("draft").megapixels == pytest.approx(0.64)
    assert tiers.get("final").megapixels == pytest.approx(2.25)


def test_the_summary_lists_each_tier() -> None:
    assert load_tiers().summary() == {
        "draft": "12 × 800² eevee",
        "final": "36 × 1500² cycles",
    }


def test_a_missing_tier_fails_by_name(tmp_path: Path) -> None:
    text = "\n".join(line for line in GOOD.splitlines() if "final" not in line)
    with pytest.raises(TierError) as caught:
        _load(tmp_path, text)
    assert "final" in str(caught.value)


def test_a_configuration_still_naming_preview_fails_as_an_unknown_tier(tmp_path: Path) -> None:
    text = GOOD + "  preview: {frames: 24, resolution: 1000, engine: eevee, timeout_multiplier: 2}\n"
    with pytest.raises(TierError) as caught:
        _load(tmp_path, text)
    message = str(caught.value)
    assert "unknown tier" in message and "preview" in message
    assert "draft" in message and "final" in message


def test_a_duplicate_tier_fails(tmp_path: Path) -> None:
    text = GOOD + "  draft: {frames: 1, resolution: 1, engine: eevee, timeout_multiplier: 1}\n"
    with pytest.raises(TierError) as caught:
        _load(tmp_path, text)
    assert "draft" in str(caught.value)


def test_an_unknown_tier_in_the_file_fails(tmp_path: Path) -> None:
    text = GOOD + "  ultra: {frames: 1, resolution: 1, engine: eevee, timeout_multiplier: 1}\n"
    with pytest.raises(TierError) as caught:
        _load(tmp_path, text)
    assert "ultra" in str(caught.value)


def test_an_unknown_key_fails(tmp_path: Path) -> None:
    text = GOOD.replace("timeout_multiplier: 1}", "timeout_multiplier: 1, samples: 64}", 1)
    with pytest.raises(TierError) as caught:
        _load(tmp_path, text)
    assert "samples" in str(caught.value)


def test_an_unknown_engine_fails(tmp_path: Path) -> None:
    with pytest.raises(TierError) as caught:
        _load(tmp_path, GOOD.replace("engine: cycles", "engine: luxcore"))
    assert "luxcore" in str(caught.value)


@pytest.mark.parametrize("bad", ["0", "-3", "1.5", "'x'", "true"])
def test_a_non_positive_or_non_integer_value_fails(tmp_path: Path, bad: str) -> None:
    with pytest.raises(TierError) as caught:
        _load(tmp_path, GOOD.replace("frames: 12", f"frames: {bad}"))
    assert "frames" in str(caught.value)


@pytest.mark.parametrize("name", ["ultra", "preview"])
def test_get_refuses_an_unknown_tier_listing_the_two(name: str) -> None:
    with pytest.raises(TierError) as caught:
        load_tiers().get(name)
    message = str(caught.value)
    assert name in message
    assert "the tiers are draft, final" in message
