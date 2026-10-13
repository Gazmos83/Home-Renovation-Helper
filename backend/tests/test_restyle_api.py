"""restyle-variants: the studio routes list a version's variants and serve their files by exact name."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.restyle import store
from tests.api_helpers import create, make_client, sign_in
from tests.blender_fakes import fake_success_launch, png_bytes


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_success_launch())
    sign_in(c)
    yield c
    c.__exit__(None, None, None)


def seed(folder: Path, name: str, created: str, **extra) -> None:
    target = store.variants_dir(folder) / name
    target.mkdir(parents=True)
    (target / "still.png").write_bytes(png_bytes(4, 4))
    (target / "scene.json").write_text(
        json.dumps({"created_at": created, "label": name.title(), "tier": "draft",
                    "note": "appearance only, not a priced material", "looks": {"carcass": name},
                    "prompt": "secret", "model": "x", **extra}),
        encoding="utf-8",
    )


def test_variants_are_listed_newest_first_with_their_pictures_and_no_developer_fields(
    client: TestClient, render_root: Path
) -> None:
    create(client)
    folder = render_root / "hall-bench" / "v1"
    seed(folder, "oak-draft", "2026-10-12T09:00:00+00:00")
    seed(folder, "walnut-draft", "2026-10-12T10:00:00+00:00")
    listed = client.get("/packages/hall-bench/versions/1/variants").json()
    assert [item["id"] for item in listed] == ["walnut-draft", "oak-draft"]
    assert listed[0]["still"] == "/packages/hall-bench/versions/1/files/variants/walnut-draft/still.png"
    assert listed[0]["note"] == "appearance only, not a priced material"
    assert not {"prompt", "model", "tokens", "cost"} & set(listed[0])
    picture = client.get(listed[0]["still"])
    assert picture.status_code == 200 and picture.headers["content-type"] == "image/png"


def test_a_version_without_variants_lists_none(client: TestClient) -> None:
    create(client)
    assert client.get("/packages/hall-bench/versions/1/variants").json() == []
    assert client.get("/packages/hall-bench/versions/9/variants").status_code == 404


def test_only_the_two_named_files_are_served_and_traversal_is_refused(
    client: TestClient, render_root: Path
) -> None:
    create(client)
    folder = render_root / "hall-bench" / "v1"
    seed(folder, "oak-draft", "2026-10-12T09:00:00+00:00")
    (store.variants_dir(folder) / "oak-draft" / "secret.txt").write_text("x", encoding="utf-8")
    base = "/packages/hall-bench/versions/1/files/variants"
    assert client.get(f"{base}/oak-draft/scene.json").status_code == 200
    assert client.get(f"{base}/oak-draft/secret.txt").status_code == 404
    assert client.get(f"{base}/missing/still.png").status_code == 404
    assert client.get(f"{base}/..%2Fstatus.json/still.png").status_code == 404


def test_the_routes_need_the_owner_cookie(migrated_database: str, render_root: Path, fake_blender: Path) -> None:
    anonymous = make_client(migrated_database, render_root, fake_blender, fake_success_launch())
    try:
        assert anonymous.get("/packages/hall-bench/versions/1/variants").status_code == 401
        assert anonymous.get("/compositions/wohnen/versions/1/variants").status_code == 401
    finally:
        anonymous.__exit__(None, None, None)


def test_a_composition_version_lists_its_variants(client: TestClient, render_root: Path) -> None:
    from app.blender import storage

    folder = storage.composition_version_dir(render_root, "wohnen", 1)
    folder.mkdir(parents=True)
    seed(folder, "japandi-draft", "2026-10-12T09:00:00+00:00", style="japandi")
    listed = client.get("/compositions/wohnen/versions/1/variants").json()
    assert listed[0]["still"] == "/compositions/wohnen/versions/1/files/variants/japandi-draft/still.png"
    assert listed[0]["style"] == "japandi"
    assert client.get(listed[0]["still"]).status_code == 200
