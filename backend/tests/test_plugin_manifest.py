"""plugins: folder manifests, loading, refused fields, migration 0006."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import make_engine
from app.plugins.loader import DEFAULT_PLUGINS_ROOT, PluginError, load_plugins
from app.plugins.manifest import ManifestRefused, parse_manifest
from conftest import BACKEND_ROOT

ALEMBIC = BACKEND_ROOT / "alembic.ini"


def _builtin(**overrides) -> dict:
    data = {
        "name": "sample",
        "description": "a sample plugin",
        "kind": "builtin",
        "role": "designer",
        "tools": ["sample_tool"],
        "enabled_by_default": True,
        "toggleable": True,
    }
    data.update(overrides)
    return data


def _https(**overrides) -> dict:
    data = {
        "name": "echo",
        "description": "an HTTPS echo plugin",
        "kind": "https",
        "role": "researcher",
        "tools": ["plugin_echo"],
        "enabled_by_default": False,
        "toggleable": True,
        "input_schema": {
            "type": "object",
            "properties": {"q": {"type": "string", "description": "query"}},
            "required": ["q"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "additionalProperties": False,
        },
        "request": {
            "method": "GET",
            "url": "https://echo.plugin-test.invalid/search/{q}",
        },
    }
    data.update(overrides)
    return data


def _refused(data: dict) -> list[dict[str, str]]:
    with pytest.raises(ManifestRefused) as caught:
        parse_manifest(data)
    return caught.value.errors


def _fields(errors: list[dict[str, str]]) -> set[str]:
    return {error["field"] for error in errors}


def _write_plugin(root: Path, name: str, manifest: dict, tool_py: str | None = None) -> Path:
    folder = root / name
    folder.mkdir()
    (folder / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    (folder / "__init__.py").write_text("", encoding="utf-8")
    if tool_py is not None:
        (folder / "tool.py").write_text(tool_py, encoding="utf-8")
    return folder / "manifest.yaml"


_STUB_TOOL = dedent(
    """\
    from pydantic import BaseModel
    from app.agent.tools.base import AgentTool, ToolContext

    class Args(BaseModel):
        q: str = ""

    sample_tool = AgentTool(name="sample_tool", description="stub", schema=Args, run=lambda a, c: "ok")
    """
)


# --- shipped plugins -----------------------------------------------------------------


def test_shipped_plugins_load_and_offer_at_least_ten_toggleable_tools() -> None:
    loaded = load_plugins(DEFAULT_PLUGINS_ROOT)
    assert len(loaded.toggleable_tool_names()) >= 10
    assert "record_brief" in loaded.tool_names()
    assert loaded.by_name["intake"].toggleable is False
    assert loaded.by_name["create_piece"].toggleable is False


def test_shipped_manifests_match_their_folder_names() -> None:
    loaded = load_plugins()
    for name, plugin in loaded.by_name.items():
        assert plugin.manifest.name == name
        assert plugin.path.parent.name == name


# --- refused fields ------------------------------------------------------------------


def test_a_missing_name_is_refused() -> None:
    data = _builtin()
    del data["name"]
    assert "name" in _fields(_refused(data))


def test_a_missing_description_is_refused() -> None:
    data = _builtin()
    del data["description"]
    assert "description" in _fields(_refused(data))


def test_a_missing_kind_is_refused() -> None:
    data = _builtin()
    del data["kind"]
    assert "kind" in _fields(_refused(data))


def test_a_missing_role_is_refused() -> None:
    data = _builtin()
    del data["role"]
    assert "role" in _fields(_refused(data))


def test_a_missing_tools_list_is_refused() -> None:
    data = _builtin()
    del data["tools"]
    assert "tools" in _fields(_refused(data))


def test_a_missing_enabled_by_default_is_refused() -> None:
    data = _builtin()
    del data["enabled_by_default"]
    assert "enabled_by_default" in _fields(_refused(data))


def test_an_unknown_field_is_refused() -> None:
    assert "code" in _fields(_refused(_builtin(code="import os")))


def test_an_unknown_role_is_refused() -> None:
    assert "role" in _fields(_refused(_builtin(role="styler")))


def test_an_unknown_kind_is_refused() -> None:
    assert "kind" in _fields(_refused(_builtin(kind="python")))


def test_an_https_remote_schema_reference_is_refused() -> None:
    data = _https()
    data["input_schema"]["properties"]["q"] = {"$ref": "https://evil.example/schema.json"}
    assert any(f.startswith("input_schema.properties.q") for f in _fields(_refused(data)))


def test_an_https_nested_object_input_is_refused() -> None:
    data = _https()
    data["input_schema"]["properties"]["filter"] = {"type": "object", "properties": {}}
    assert any(f.startswith("input_schema.properties.filter") for f in _fields(_refused(data)))


def test_an_https_non_get_method_is_refused() -> None:
    data = _https()
    data["request"]["method"] = "POST"
    assert "request.method" in _fields(_refused(data))


def test_an_https_plugin_enabled_by_default_is_refused() -> None:
    assert "enabled_by_default" in _fields(_refused(_https(enabled_by_default=True)))


@pytest.mark.parametrize(
    "url",
    [
        "http://echo.plugin-test.invalid/search/{q}",
        "https://user:secret@echo.plugin-test.invalid/search/{q}",
        "https://echo.plugin-test.invalid:8443/search/{q}",
        "https://echo.plugin-test.invalid/search/{q}?key=abc",
        "https://echo.plugin-test.invalid/search/{q}#frag",
        "https://{q}.plugin-test.invalid/search",
    ],
)
def test_an_unsafe_https_url_is_refused(url: str) -> None:
    data = _https()
    data["request"]["url"] = url
    assert "request.url" in _fields(_refused(data))


def test_a_placeholder_naming_no_input_is_refused() -> None:
    data = _https()
    data["request"]["url"] = "https://echo.plugin-test.invalid/search/{session}"
    errors = _refused(data)
    assert any("session" in e["message"] for e in errors)


# --- loader --------------------------------------------------------------------------


def test_two_plugins_claiming_a_tool_names_both_files(tmp_path: Path) -> None:
    stub = _STUB_TOOL.replace("sample_tool", "cut_list")
    first = _write_plugin(tmp_path, "alpha", _builtin(name="alpha", tools=["cut_list"]), stub)
    second = _write_plugin(tmp_path, "beta", _builtin(name="beta", tools=["cut_list"]), stub)
    with pytest.raises(PluginError) as caught:
        load_plugins(tmp_path)
    message = str(caught.value)
    assert "cut_list" in message
    assert str(first) in message
    assert str(second) in message


def test_an_unknown_role_in_a_file_names_the_file(tmp_path: Path) -> None:
    path = _write_plugin(tmp_path, "sample", _builtin(role="styler"), _STUB_TOOL)
    with pytest.raises(PluginError) as caught:
        load_plugins(tmp_path)
    assert str(path) in str(caught.value)
    assert "role" in str(caught.value)


def test_a_builtin_tool_with_no_implementation_names_the_file(tmp_path: Path) -> None:
    path = _write_plugin(tmp_path, "sample", _builtin(), tool_py="from pydantic import BaseModel\n")
    with pytest.raises(PluginError) as caught:
        load_plugins(tmp_path)
    assert str(path) in str(caught.value)
    assert "sample_tool" in str(caught.value)


def test_an_https_host_not_on_the_allow_list_names_the_manifest_and_the_host(tmp_path: Path) -> None:
    path = _write_plugin(tmp_path, "echo", _https(name="echo"))
    with pytest.raises(PluginError) as caught:
        load_plugins(tmp_path, allowed_hosts=())
    message = str(caught.value)
    assert str(path) in message
    assert "echo.plugin-test.invalid" in message


def test_an_https_plugin_loads_when_the_host_is_allowed(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "echo", _https(name="echo"))
    loaded = load_plugins(tmp_path, allowed_hosts={"echo.plugin-test.invalid"})
    assert "plugin_echo" in loaded.tool_names()
    assert loaded.by_name["echo"].kind == "https"
    assert loaded.by_name["echo"].enabled_by_default is False


# --- migration -----------------------------------------------------------------------


def _alembic(database_url: str) -> Config:
    config = Config(str(ALEMBIC))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_upgrade_and_downgrade_leave_no_drift(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", migrated_database)
    config = _alembic(migrated_database)
    command.downgrade(config, "0003_apartments_uploads")
    engine = make_engine(migrated_database)
    try:
        with Session(engine) as session:
            tables = set(session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).scalars())
        assert "thread_tool_settings" not in tables
        assert "plugin_invocations" not in tables
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = make_engine(migrated_database)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
        with Session(engine) as session:
            columns = set(
                session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'model_usage'"
                    )
                ).scalars()
            )
        assert "estimated_tokens" in columns
    finally:
        engine.dispose()
    app_diff = [
        item
        for item in diff
        if "checkpoints" not in repr(item) and "checkpoint_" not in repr(item)
    ]
    assert app_diff == [], f"schema drift after upgrade/downgrade: {app_diff!r}"
