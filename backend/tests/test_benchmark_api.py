"""render-guard: the developer-gated benchmark routes."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.blender.launch import LaunchResult
from app.config import Settings
from app.main import create_app
from conftest import OWNER_EMAIL, OWNER_PASSWORD
from tests.api_helpers import create, reset_owner, sign_in
from tests.blender_fakes import (
    arg_value,
    fake_failure_launch,
    out_dir_from_argv,
    png_bytes,
    write_build_files,
)

BENCH = "/admin/render/benchmark"


def fake_benchmark_launch(render_seconds: float = 2.4):
    async def _launch(argv: list[str], cwd: Path, timeout: float) -> LaunchResult:
        out = out_dir_from_argv(argv)
        if any(part.endswith("build_custom_build.py") for part in argv):
            write_build_files(out)
        else:
            assert arg_value(argv, "--tier-resolution") == "1000"
            out.mkdir()
            (out / "still.png").write_bytes(png_bytes(1000, 1000))
            (out / "scene.json").write_text(
                json.dumps({"render_seconds": render_seconds, "blender_version": "5.2.1 LTS"}),
                encoding="utf-8",
            )
        return LaunchResult(0, "", False)

    return _launch


def build_client(url: str, render_root: Path, binary: Path, launch, *, dev: bool) -> TestClient:
    reset_owner(url)
    app = create_app(
        Settings(
            database_url=url,
            openrouter_api_key="sk-or-test",
            cors_origins="http://localhost:5173",
            owner_email=OWNER_EMAIL,
            owner_password=OWNER_PASSWORD,
            gateway_probe_enabled=False,
            dev_panel_enabled=dev,
            render_root=render_root,
            blender_bin=binary,
            _env_file=None,
        )
    )
    app.state.blender_launch = launch
    client = TestClient(app)
    client.__enter__()
    with Session(app.state.engine) as session:
        session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'render:%'"))
        session.commit()
    return client


@pytest.fixture
def dev_client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = build_client(migrated_database, render_root, fake_blender, fake_benchmark_launch(), dev=True)
    sign_in(c)
    yield c
    c.__exit__(None, None, None)


def test_the_panel_off_hides_both_routes(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    c = build_client(migrated_database, render_root, fake_blender, fake_benchmark_launch(), dev=False)
    sign_in(c)
    assert c.get(BENCH).status_code == 404
    assert c.post(BENCH).status_code == 404
    c.__exit__(None, None, None)


def test_not_signed_in_is_401_with_the_panel_on(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    c = build_client(migrated_database, render_root, fake_blender, fake_benchmark_launch(), dev=True)
    assert c.get(BENCH).status_code == 401 and c.post(BENCH).status_code == 401
    c.__exit__(None, None, None)


def test_before_any_run_there_is_no_benchmark(dev_client: TestClient) -> None:
    assert dev_client.get(BENCH).json() == {
        "benchmark": None, "cycles_multiplier": 30.0, "cycles_calibrated": False,
    }


def test_running_stores_a_value_readable_afterwards(dev_client: TestClient, render_root: Path) -> None:
    result = dev_client.post(BENCH)
    assert result.status_code == 200
    assert result.json()["benchmark"]["seconds_per_megapixel"] == pytest.approx(2.4)
    assert dev_client.get(BENCH).json()["benchmark"]["blender_version"] == "5.2.1 LTS"
    assert (render_root / "benchmark" / "frame" / "still.png").is_file()


def test_a_failed_benchmark_is_a_stated_502_and_stores_nothing(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    c = build_client(migrated_database, render_root, fake_blender, fake_failure_launch, dev=True)
    sign_in(c)
    response = c.post(BENCH)
    assert response.status_code == 502
    assert response.json()["detail"]["failure_class"] == "benchmark_failed"
    assert c.get(BENCH).json()["benchmark"] is None
    c.__exit__(None, None, None)


def test_a_missing_binary_is_a_503(
    migrated_database: str, render_root: Path, tmp_path: Path
) -> None:
    c = build_client(migrated_database, render_root, tmp_path / "gone", fake_benchmark_launch(), dev=True)
    sign_in(c)
    assert c.post(BENCH).status_code == 503
    c.__exit__(None, None, None)


def test_the_guard_accepts_a_draft_only_after_the_benchmark_exists(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    from tests.blender_fakes import fake_pipeline_launch

    pipeline = fake_pipeline_launch()
    bench = fake_benchmark_launch()

    async def both(argv, cwd, timeout):
        # The reference build is the same script as a package build.
        if arg_value(argv, "--tier-resolution") == "1000":
            return await bench(argv, cwd, timeout)
        return await pipeline(argv, cwd, timeout)

    c = build_client(migrated_database, render_root, fake_blender, both, dev=True)
    sign_in(c)
    assert create(c).status_code == 202
    url = "/packages/hall-bench/versions/1/renders"
    before = c.post(url, json={"kind": "still", "tier": "draft"})
    assert before.status_code == 409 and before.json()["detail"]["failure_class"] == "benchmark_missing"
    assert c.post(BENCH).status_code == 200
    after = c.post(url, json={"kind": "still", "tier": "draft"})
    assert after.status_code == 202
    c.__exit__(None, None, None)
