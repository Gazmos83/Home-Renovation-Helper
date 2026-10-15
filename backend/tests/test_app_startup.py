"""Assembly: the app boots, migrates-owned schema served, and the startup
summary reports tracing and routing without a secret (tasks 8.1, 6.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import Settings
from app.db.migrate import head_revision
from app.db.session import make_engine
from app.main import create_app
from conftest import OWNER_EMAIL, OWNER_PASSWORD

BACKEND = Path(__file__).resolve().parents[1]


def _settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        openrouter_api_key="sk-or-v1-deadbeefsecret",
        cors_origins="http://localhost:5173",
        owner_email=OWNER_EMAIL,
        owner_password=OWNER_PASSWORD,
        gateway_probe_enabled=False,
        _env_file=None,
    )


def test_the_app_boots_against_the_test_database_and_health_answers(
    migrated_database: str,
) -> None:
    app = create_app(_settings(migrated_database))
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert app.state.routing is not None
        assert app.state.tracing is not None
        assert app.state.profiles is not None


def test_the_startup_summary_names_tracing_and_routing_without_a_secret(
    migrated_database: str, capsys,
) -> None:
    """`capsys`, not `caplog`: `configure_logging()` replaces the root logger's
    handlers with its own JSON-to-stdout one."""
    settings = _settings(migrated_database)
    with TestClient(create_app(settings)):
        pass

    lines = [line for line in capsys.readouterr().out.strip().splitlines() if line.startswith("{")]
    records = [json.loads(line) for line in lines]
    summary = [r for r in records if r.get("message") == "service ready"]
    assert len(summary) == 1
    record = summary[0]
    assert record["tracing"] == "off"
    assert record["probe"] == "skipped"
    assert record["schema"] == head_revision()
    assert record["routing"]["reviewer"] == "deepseek/deepseek-v4.1-flash"

    # No secret anywhere in any record.
    for r in records:
        assert settings.openrouter_api_key.get_secret_value() not in json.dumps(r)
        assert settings.owner_password.get_secret_value() not in json.dumps(r)


def _ready_record(capsys) -> dict:
    lines = [line for line in capsys.readouterr().out.strip().splitlines() if line.startswith("{")]
    [record] = [r for r in map(json.loads, lines) if r.get("message") == "service ready"]
    return record


def test_the_summary_names_the_tiers_the_benchmark_and_generation(
    migrated_database: str, tmp_path, capsys
) -> None:
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.db.session import make_engine

    engine = make_engine(migrated_database)
    with Session(engine) as session:
        session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'render:%'"))
        session.commit()
    engine.dispose()
    settings = _settings(migrated_database).model_copy(update={"blender_bin": tmp_path / "gone"})

    with TestClient(create_app(settings)):
        pass

    record = _ready_record(capsys)
    assert record["tiers"] == {
        "draft": "12 × 800² eevee",
        "final": "36 × 1500² cycles",
    }
    assert record["benchmark"] == "missing"
    assert record["generation"] == "off"


def test_the_summary_reports_a_stored_benchmark_without_running_one(
    migrated_database: str, capsys
) -> None:
    from app.db.session import make_engine
    from app.render.benchmark_store import write_benchmark

    engine = make_engine(migrated_database)
    write_benchmark(engine, 2.5)
    engine.dispose()
    with TestClient(create_app(_settings(migrated_database))):
        pass
    assert _ready_record(capsys)["benchmark"] == "stored"


def test_startup_brings_a_behind_schema_to_head(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", migrated_database)
    config = Config(str(BACKEND / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    previous = ScriptDirectory.from_config(config).get_revision(head).down_revision
    assert previous, "there must be an older revision to stand behind"
    command.downgrade(config, previous)
    engine = make_engine(migrated_database)
    try:
        with TestClient(create_app(_settings(migrated_database))):
            pass
        with engine.connect() as connection:
            assert MigrationContext.configure(connection).get_current_revision() == head
    finally:
        command.upgrade(config, "head")
        engine.dispose()


def test_the_app_registers_the_render_state_and_routes(migrated_database: str) -> None:
    app = create_app(_settings(migrated_database))
    assert app.state.blender_launch is None, "production falls through to the real launcher"
    assert app.state.blender_semaphore._value == 1, "one Blender process at a time"
    assert [name for name, _ in app.state.tiers.items()] == ["draft", "final"]
    paths = set(app.openapi()["paths"])
    assert {"/packages", "/packages/{package_id}/spec",
            "/packages/{package_id}/versions/{version}/renders",
            "/admin/render/benchmark"} <= paths


def test_a_pod_left_running_is_deleted_at_startup_and_the_pod_at_shutdown(
    migrated_database: str, tmp_path: Path
) -> None:
    """render-pod-lifecycle: only app-named pods are touched, against an in-memory RunPod."""
    from pydantic import SecretStr

    from app.render.offload.runpod import RunPodClient
    from tests.offload_fakes import FakeRunPod

    key, known = tmp_path / "id_ed25519", tmp_path / "known_hosts"
    key.write_text("PRIVATE", encoding="utf-8")
    known.write_text("hra-render-pod ssh-ed25519 AAAA", encoding="utf-8")
    settings = _settings(migrated_database).model_copy(
        update={
            "render_offload_user": "root",
            "render_offload_key_path": key,
            "render_offload_known_hosts_path": known,
            "render_offload_blender": "/workspace/blender-5.2.1-linux-x64/blender",
            "render_offload_runpod_api_key": SecretStr("rpa_SECRETKEYVALUE"),
            "render_offload_runpod_network_volume_id": "vol123",
            "render_offload_runpod_gpu_type": "NVIDIA GeForce RTX 4090",
            "render_offload_runpod_image": "runpod/base:0.6.2",
        }
    )
    app = create_app(settings)
    pod = app.state.offload.pod
    assert pod is not None
    fake = FakeRunPod()
    pod.client = RunPodClient(SecretStr("rpa_SECRETKEYVALUE"), transport=fake.transport)
    left_over = fake.add_pod("hra-render")
    other = fake.add_pod("someone-else")
    with TestClient(app):
        assert fake.deleted == [left_over] and other in fake.pods
        current = fake.add_pod("hra-render")
        pod.pod_id, pod.state = current, "running"
    assert fake.deleted == [left_over, current] and other in fake.pods
    engine = make_engine(migrated_database)
    with engine.begin() as connection:  # the recorded pod sessions
        connection.execute(text("DELETE FROM render_pod_sessions"))
    engine.dispose()

