"""Load every plugin folder at startup. Errors name the manifest file."""

from __future__ import annotations

import importlib.util
import logging
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

from app.agent.tools.base import AgentTool
from app.plugins.manifest import (
    BuiltinManifest,
    HttpsManifest,
    ManifestRefused,
    parse_manifest,
)

logger = logging.getLogger("app")

DEFAULT_PLUGINS_ROOT: Final = Path(__file__).resolve().parents[2] / "plugins"


class PluginError(ValueError):
    """A plugin folder cannot be loaded. The message names the manifest file."""


@dataclass
class LoadedPlugin:
    manifest: BuiltinManifest | HttpsManifest
    path: Path
    tools: dict[str, AgentTool] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def kind(self) -> str:
        return self.manifest.kind

    @property
    def role(self) -> str:
        return self.manifest.role

    @property
    def agents(self) -> tuple[str, ...]:
        """The agents whose instruction headers may name this plugin's tools."""
        return (self.manifest.role, *getattr(self.manifest, "also_for", ()))

    @property
    def toggleable(self) -> bool:
        return self.manifest.toggleable

    @property
    def enabled_by_default(self) -> bool:
        return self.manifest.enabled_by_default


@dataclass
class Plugins:
    """The loaded set: by name, tool → plugin, tools by role."""

    by_name: dict[str, LoadedPlugin]
    tool_to_plugin: dict[str, str]
    root: Path

    def tool_names(self) -> frozenset[str]:
        return frozenset(self.tool_to_plugin)

    def builtin_tools(self) -> dict[str, AgentTool]:
        tools: dict[str, AgentTool] = {}
        for plugin in self.by_name.values():
            tools.update(plugin.tools)
        return tools

    def plugin_for_tool(self, tool: str) -> LoadedPlugin | None:
        name = self.tool_to_plugin.get(tool)
        return self.by_name.get(name) if name else None

    def toggleable_tool_names(self) -> list[str]:
        names: list[str] = []
        for plugin in self.by_name.values():
            if plugin.toggleable:
                names.extend(plugin.manifest.tools)
        return names

    def https_plugins(self) -> list[LoadedPlugin]:
        return [p for p in self.by_name.values() if p.kind == "https"]


def _read_yaml(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PluginError(f"{path}: the manifest could not be read: {error}") from None
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as error:
        raise PluginError(f"{path}: the manifest is not valid YAML: {error}") from None


def _load_builtin_tools(plugin: LoadedPlugin) -> dict[str, AgentTool]:
    tool_path = plugin.path.parent / "tool.py"
    if not tool_path.is_file():
        raise PluginError(f"{plugin.path}: built-in implementation is missing")
    spec = importlib.util.spec_from_file_location(
        f"hra_plugin_{plugin.name}_{tool_path.resolve().as_posix().replace('/', '_')}",
        tool_path,
    )
    if spec is None or spec.loader is None:
        raise PluginError(f"{plugin.path}: built-in implementation could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:  # noqa: BLE001 - the file is named in the message
        raise PluginError(
            f"{plugin.path}: built-in implementation could not be imported: {type(error).__name__}: {error}"
        ) from None
    tools: dict[str, AgentTool] = {}
    for name in plugin.manifest.tools:
        found = getattr(module, name, None)
        if not isinstance(found, AgentTool) or found.name != name:
            raise PluginError(f"{plugin.path}: built-in tool {name!r} has no implementation")
        tools[name] = found
    return tools


def load_plugins(
    root: Path | None = None,
    *,
    allowed_hosts: Iterable[str] = (),
) -> Plugins:
    """Load every folder under `root` that holds a `manifest.yaml`.

    A missing field, an unknown field, a tool named by two plugins, a built-in
    tool with no implementation, an unknown role, or an HTTPS host not on the
    allow-list stops the load naming the file.
    """
    base = root or DEFAULT_PLUGINS_ROOT
    if not base.is_dir():
        raise PluginError(f"{base}: the plugins directory is missing")

    allowed = frozenset(h.lower() for h in allowed_hosts)
    loaded: dict[str, LoadedPlugin] = {}
    tool_to_plugin: dict[str, str] = {}
    tool_files: dict[str, Path] = {}

    for folder in sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith("_")):
        manifest_path = folder / "manifest.yaml"
        if not manifest_path.is_file():
            continue
        data = _read_yaml(manifest_path)
        try:
            manifest = parse_manifest(data, path=str(manifest_path))
        except ManifestRefused as error:
            raise PluginError(str(error)) from None
        if manifest.name != folder.name:
            raise PluginError(
                f"{manifest_path}: the name {manifest.name!r} must match the folder {folder.name!r}"
            )
        if manifest.name in loaded:
            raise PluginError(
                f"{manifest_path}: plugin {manifest.name!r} is also declared in {loaded[manifest.name].path}"
            )
        if isinstance(manifest, HttpsManifest) and manifest.request.host not in allowed:
            raise PluginError(
                f"{manifest_path}: the host {manifest.request.host!r} is not an approved plugin host"
            )
        plugin = LoadedPlugin(manifest=manifest, path=manifest_path)
        if isinstance(manifest, BuiltinManifest):
            plugin.tools = _load_builtin_tools(plugin)
        for tool in manifest.tools:
            if tool in tool_to_plugin:
                raise PluginError(
                    f"{manifest_path}: tool {tool!r} is also declared in {tool_files[tool]}"
                )
            tool_to_plugin[tool] = manifest.name
            tool_files[tool] = manifest_path
        loaded[manifest.name] = plugin

    logger.info(
        "plugins loaded",
        extra={
            "context": {
                "count": len(loaded),
                "tools": sorted(tool_to_plugin),
            }
        },
    )
    return Plugins(by_name=loaded, tool_to_plugin=tool_to_plugin, root=base)
