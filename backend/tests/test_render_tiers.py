"""render-guard: tiers come from configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.render.tiers import TierError, load_tiers

GOOD = """
tiers:
  draft: {frames: 12, resolution: 600, engine: eevee, timeout_multiplier: 1}
  preview: {frames: 24, resolution: 1000, engine: eevee, timeout_multiplier: 2}
  final: {frames: 36, resolution: 1500, engine: cycles, timeout_multiplier: 24}
"""


def _load(tmp_path: Path, text: str):
    path = tmp_path / "render.yaml"
    path.write_text(text, encoding="utf-8")
    return load_tiers(path)


def test_the_shipped_tiers_load() -> None:
    tiers = load_tiers()
    draft, preview, final = (tiers.get(n) for n in ("draft", "preview", "final"))
    assert (draft.frames, draft.resolution, draft.engine) == (12, 600, "eevee")
    assert (preview.frames, preview.resolution, preview.engine) == (24, 1000, "eevee")
    assert (final.frames, final.resolution, final.engine) == (36, 1500, "cycles")
    assert final.blender_engine == "CYCLES"
    assert draft.blender_engine == "BLENDER_EEVEE"


def test_megapixels() -> None:
    tiers = load_tiers()
    assert tiers.get("draft").megapixels == pytest.approx(0.36)
    assert tiers.get("final").megapixels == pytest.approx(2.25)


def test_the_summary_lists_each_tier() -> None:
    assert load_tiers().summary() == {
        "draft": "12 × 600² eevee",
        "preview": "24 × 1000² eevee",
        "final": "36 × 1500² cycles",
    }


def test_a_missing_tier_fails_by_name(tmp_path: Path) -> None:
    text = "\n".join(line for line in GOOD.splitlines() if "preview" not in line)
    with pytest.raises(TierError) as caught:
        _load(tmp_path, text)
    assert "preview" in str(caught.value)


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


def test_get_refuses_an_unknown_tier_listing_the_three() -> None:
    with pytest.raises(TierError) as caught:
        load_tiers().get("ultra")
    message = str(caught.value)
    assert "ultra" in message
    for name in ("draft", "preview", "final"):
        assert name in message
