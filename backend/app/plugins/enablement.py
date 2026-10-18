"""Global plugin enablement (`plugin:<name>`); there are no per-conversation switches."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import OperatorSetting
from app.plugins.loader import Plugins

_PLUGIN_PREFIX = "plugin:"


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


def enabled_plugin_names(
    session: Session, plugins: Plugins, thread_id: UUID | None
) -> set[str]:
    """Plugins that may bind tools: the globally enabled ones, in every thread.

    `thread_id` is kept for the call sites; no per-thread setting is read (studio-navigation-tidy).
    """
    return {name for name in plugins.by_name if global_enabled(session, plugins, name)}
