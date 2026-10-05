"""The turntable viewer page, without a browser."""

from __future__ import annotations

import pytest

from app.render.viewer import render_viewer


def test_the_frame_count_is_filled_in_everywhere() -> None:
    page = render_viewer(12, title="Hall bench", meta="600×600 BLENDER_EEVEE")
    assert "const frameCount = 12;" in page
    assert "12 frames" in page and "Hall bench" in page
    assert "{{" not in page, "no placeholder is left"


def test_the_page_reads_the_published_frame_names() -> None:
    page = render_viewer(3)
    assert "frames/frame_${pad(n)}.png" in page and 'src="frames/frame_000.png"' in page


def test_the_gestures_wrap_at_both_ends() -> None:
    page = render_viewer(3)
    for gesture in ("mousedown", "wheel", "ArrowLeft", "ArrowRight", "touchmove"):
        assert gesture in page
    assert "((n % frameCount) + frameCount) % frameCount" in page


def test_the_title_is_escaped() -> None:
    assert "<script>x" not in render_viewer(2, title="<script>x</script>")


@pytest.mark.parametrize("bad", [0, -1, True, "12"])
def test_a_bad_frame_count_is_refused(bad) -> None:
    with pytest.raises(ValueError):
        render_viewer(bad)
