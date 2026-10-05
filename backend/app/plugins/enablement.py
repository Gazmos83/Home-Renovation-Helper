"""Global (`plugin:<name>`) and per-thread plugin enablement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import OperatorSetting, ThreadToolSetting
from app.plugins.loader import Plugins

_PLUGIN_PREFIX = "plugin:"


class EnablementRefused(ValueError):
    """A toggle the owner is not allowed to make."""

    def __init__(self, reason: str, *, plugin: str, code: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.plugin = plugin
        self.code = code


def _global_key(name: str) -> str:
    return _PLUGIN_PREFIX + name


def global_enabled(session: Session, plugins: Plugins, name: str) -> bool:
    plugin = plugins.by_name.get(name)
    if plugin is None:
        return False
    row = session.get(OperatorSetting, _global_key(name))
    if row is None:
        return plugin.enabled_by_default
    return row.value == "on"


def set_global_enabled(session: Session, name: str, enabled: bool) -> None:
    key = _global_key(name)
    row = session.get(OperatorSetting, key)
    now = datetime.now(UTC)
    value = "on" if enabled else "off"
    if row is None:
        session.add(OperatorSetting(key=key, value=value, updated_at=now))
    else:
        row.value = value
        row.updated_at = now


def thread_enabled(
    session: Session, plugins: Plugins, thread_id: UUID, name: str
) -> bool:
    plugin = plugins.by_name[name]
    if not plugin.toggleable:
        return True
    row = session.get(ThreadToolSetting, (thread_id, name))
    if row is None:
        return plugin.enabled_by_default
    return row.enabled


def set_thread_enabled(
    session: Session, plugins: Plugins, thread_id: UUID, name: str, enabled: bool
) -> ThreadToolSetting:
    plugin = plugins.by_name.get(name)
    if plugin is None:
        raise EnablementRefused(f"unknown plugin {name!r}", plugin=name, code="unknown_plugin")
    if not plugin.toggleable:
        raise EnablementRefused(
            f"{name} is not toggleable", plugin=name, code="not_toggleable"
        )
    if not global_enabled(session, plugins, name):
        raise EnablementRefused(
            f"{name} is switched off for the whole service", plugin=name, code="globally_disabled"
        )
    row = session.get(ThreadToolSetting, (thread_id, name))
    now = datetime.now(UTC)
    if row is None:
        row = ThreadToolSetting(thread_id=thread_id, plugin=name, enabled=enabled, updated_at=now)
        session.add(row)
    else:
        row.enabled = enabled
        row.updated_at = now
    return row


def enabled_plugin_names(
    session: Session, plugins: Plugins, thread_id: UUID | None
) -> set[str]:
    """Plugins that may bind tools for this thread (or with no thread, globally)."""
    names: set[str] = set()
    for plugin in plugins.by_name.values():
        if not global_enabled(session, plugins, plugin.name):
            continue
        if thread_id is None or not plugin.toggleable:
            names.add(plugin.name)
            continue
        if thread_enabled(session, plugins, thread_id, plugin.name):
            names.add(plugin.name)
    return names


@dataclass(frozen=True)
class ToolToggle:
    plugin: str
    description: str
    enabled: bool
    toggleable: bool
    globally_enabled: bool


def list_thread_toggles(
    session: Session, plugins: Plugins, thread_id: UUID
) -> list[ToolToggle]:
    """Every plugin as the conversations page shows it."""
    rows: list[ToolToggle] = []
    for name in sorted(plugins.by_name):
        plugin = plugins.by_name[name]
        globally = global_enabled(session, plugins, name)
        if plugin.toggleable:
            enabled = thread_enabled(session, plugins, thread_id, name) if globally else False
        else:
            enabled = globally
        rows.append(
            ToolToggle(
                plugin=name,
                description=plugin.manifest.description,
                enabled=enabled,
                toggleable=plugin.toggleable and globally,
                globally_enabled=globally,
            )
        )
    return rows
