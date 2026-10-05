"""The scrollable turntable page written beside a turntable's frames.

Standard library only, so the generators write it from inside Blender. The
template is the predecessor's `reference/viewer.html` (drag, scroll, arrow keys
and touch, wrapping at both ends) with the frame count filled in from the tier.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Final

TEMPLATE: Final = Path(__file__).with_name("viewer.html")


def render_viewer(frame_count: int, *, title: str = "Turntable", meta: str = "") -> str:
    if isinstance(frame_count, bool) or not isinstance(frame_count, int) or frame_count < 1:
        raise ValueError("frame_count must be a positive integer")
    return (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("{{TITLE}}", html.escape(title))
        .replace("{{META}}", html.escape(meta))
        .replace("{{FRAME_COUNT}}", str(frame_count))
    )
