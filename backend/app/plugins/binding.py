"""HTTPS plugins as `AgentTool` objects, and the tools a specialist binds."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.agent.prompts import neutralise
from app.agent.tools.base import AgentTool, ToolContext, parse_args
from app.plugins.enablement import enabled_plugin_names
from app.plugins.executor import PluginExecutor
from app.plugins.https_schema import args_model, output_field_notes
from app.plugins.loader import LoadedPlugin, Plugins
from app.plugins.manifest import HttpsManifest


def https_tool(plugin: LoadedPlugin, executor: PluginExecutor) -> AgentTool:
    """One HTTPS plugin as an `AgentTool`. Ownership comes from `ToolContext`."""
    manifest = plugin.manifest
    if not isinstance(manifest, HttpsManifest):
        raise TypeError(f"{plugin.name} is not an HTTPS plugin")
    schema = args_model(manifest)
    notes = output_field_notes(manifest)
    description = neutralise(manifest.description)
    if notes:
        description = description + "\n\n" + neutralise(notes)
    tool_name = manifest.tools[0]

    def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
        args, problem = parse_args(schema, arguments)
        if args is None:
            return problem
        return executor.invoke(
            manifest, args.model_dump(exclude_none=True), thread_id=ctx.thread_id
        )

    return AgentTool(name=tool_name, description=description, schema=schema, run=run)


def attach_https_tools(plugins: Plugins, executor: PluginExecutor) -> dict[str, AgentTool]:
    """Build HTTPS `AgentTool`s and store them on each loaded plugin."""
    tools: dict[str, AgentTool] = {}
    for plugin in plugins.https_plugins():
        tool = https_tool(plugin, executor)
        plugin.tools[tool.name] = tool
        tools[tool.name] = tool
    return tools


def bound_tool_names(
    session: Session,
    plugins: Plugins,
    *,
    thread_id: UUID | None,
    role: str,
    header_tools: tuple[str, ...],
) -> list[str]:
    """The tools a specialist binds this turn.

    Header tools whose plugin is globally on, plus enabled HTTPS tools for the
    same role. No per-conversation setting changes this.
    """
    enabled = enabled_plugin_names(session, plugins, thread_id)
    names: list[str] = []
    for tool in header_tools:
        plugin = plugins.plugin_for_tool(tool)
        if plugin is not None and plugin.name in enabled:
            names.append(tool)
    for plugin in plugins.https_plugins():
        if plugin.role == role and plugin.name in enabled:
            names.extend(plugin.manifest.tools)
    return names
