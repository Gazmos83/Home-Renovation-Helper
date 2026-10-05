"""The agents' tools.

Each tool is a module here; `KNOWN_TOOLS` is the closed set an instruction
file's header may name, so a typo or an invented tool stops startup naming the
file. `GATED_TOOLS` pause for the owner's answer before they run.
"""

from __future__ import annotations

from typing import Final

KNOWN_TOOLS: Final = frozenset(
    {
        "record_brief",
        "create_piece",
        "revise_package",
        "cut_list",
        "room_fit",
        "blender_build",
        "render_turntable",
    }
)

# `render_turntable` is gated only for the `final` tier (the guard's own pause).
GATED_TOOLS: Final = frozenset({"record_brief", "create_piece", "revise_package"})


def all_tools() -> dict:
    """Every tool by name. Imported on demand so the name sets above stay light."""
    from app.agent.tools.blender_build import blender_build
    from app.agent.tools.create_piece import create_piece
    from app.agent.tools.cut_list import cut_list
    from app.agent.tools.record_brief import record_brief
    from app.agent.tools.render_turntable import render_turntable
    from app.agent.tools.revise_package import revise_package
    from app.agent.tools.room_fit import room_fit

    tools = {
        tool.name: tool
        for tool in (
            record_brief,
            create_piece,
            revise_package,
            cut_list,
            room_fit,
            blender_build,
            render_turntable,
        )
    }
    assert set(tools) == KNOWN_TOOLS
    return tools
