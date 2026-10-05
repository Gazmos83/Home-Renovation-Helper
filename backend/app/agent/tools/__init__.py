"""The agents' tools.

`KNOWN_TOOLS` is the closed set the plugin manifests declare; an instruction
file's header may name only those. Implementations live in `backend/plugins/`.
`base.py` and `shared.py` stay here as the framework those modules import.
"""

from __future__ import annotations

from typing import Final

from app.plugins.loader import Plugins, load_plugins

_PLUGINS: Plugins = load_plugins()
KNOWN_TOOLS: Final = _PLUGINS.tool_names()


def loaded_plugins() -> Plugins:
    return _PLUGINS


def all_tools() -> dict:
    """Every built-in tool by name."""
    tools = _PLUGINS.builtin_tools()
    assert set(tools) == KNOWN_TOOLS or set(tools) <= KNOWN_TOOLS
    return tools


def tool_roles() -> dict[str, str]:
    """Tool name → plugin role, for the instruction loader."""
    roles: dict[str, str] = {}
    for name, plugin in _PLUGINS.tool_to_plugin.items():
        roles[name] = _PLUGINS.by_name[plugin].role
    return roles
