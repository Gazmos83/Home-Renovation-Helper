"""furniture-packages: a job left running by a previous process fails at startup."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.blender import storage
from app.config import Settings
from app.main import create_app
from conftest import OWNER_EMAIL, OWNER_PASSWORD


def _settings(database_url: str, render_root: Path) -> Settings:
    return Settings(
        database_url=database_url,
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        owner_email=OWNER_EMAIL,
        owner_password=OWNER_PASSWORD,
        gateway_probe_enabled=False,
        render_root=render_root,
        _env_file=None,
    )


def test_a_running_build_and_a_queued_render_read_failed_after_boot(
    migrated_database: str, render_root: Path
) -> None:
    folder = storage.version_dir(render_root, "desk", 1)
    storage.write_status(folder, status="running", started_at="t0")
    storage.write_render_status(folder, "turntable", status="queued", tier="draft")
    done = storage.version_dir(render_root, "done", 1)
    storage.write_status(done, status="succeeded")

    with TestClient(create_app(_settings(migrated_database, render_root))):
        pass

    status = storage.read_status(folder)
    assert status["status"] == "failed" and "restart" in status["error"]
    assert status["renders"]["turntable"]["status"] == "failed"
    assert "restart" in status["renders"]["turntable"]["error"]
    assert storage.read_status(done)["status"] == "succeeded", "finished work is untouched"


def test_boot_with_no_render_root_is_harmless(migrated_database: str, tmp_path: Path) -> None:
    with TestClient(create_app(_settings(migrated_database, tmp_path / "nothing-here"))) as client:
        assert client.get("/health").status_code == 200


def test_the_sweep_counts_what_it_changed(render_root: Path) -> None:
    folder = storage.version_dir(render_root, "desk", 1)
    storage.write_status(folder, status="queued")
    storage.write_render_status(folder, "still", status="running")
    assert storage.sweep_orphaned_statuses(render_root) == 2
    assert storage.sweep_orphaned_statuses(render_root) == 0
