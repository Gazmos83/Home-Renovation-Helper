"""plan-uploads: uploading, validating, storing and serving conversation images."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import png_bytes
from tests.conftest import clean_house_file

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200


@pytest.fixture
def upload_root(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def client(
    migrated_database: str, render_root: Path, fake_blender: Path, upload_root: Path
) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, None)
    c.app.state.settings.upload_root = upload_root
    c.app.state.settings.upload_max_bytes = 20_000
    c.app.state.settings.upload_max_per_thread = 3
    clean_house_file(c.app.state.engine)
    sign_in(c)
    yield c
    clean_house_file(c.app.state.engine)
    c.__exit__(None, None, None)


def thread(client: TestClient) -> str:
    return client.post("/chat/threads", json={}).json()["thread_id"]


def post(client: TestClient, thread_id: str, content: bytes, name: str = "plan.png"):
    return client.post(f"/chat/threads/{thread_id}/uploads", files={"file": (name, content, "image/png")})


def test_a_png_and_a_jpeg_are_accepted_listed_and_served(client: TestClient, upload_root: Path) -> None:
    t = thread(client)
    first = post(client, t, png_bytes(40, 30))
    second = post(client, t, JPEG, "photo.jpg")
    assert first.status_code == 201 and second.status_code == 201
    assert (first.json()["kind"], second.json()["kind"]) == ("png", "jpeg")
    assert first.json()["size_bytes"] == len(png_bytes(40, 30))

    listed = client.get(f"/chat/threads/{t}/uploads").json()
    assert [u["upload_id"] for u in listed] == [first.json()["upload_id"], second.json()["upload_id"]]

    fetched = client.get(f"/uploads/{first.json()['upload_id']}")
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/png"
    assert fetched.headers["x-content-type-options"] == "nosniff"
    assert fetched.content == png_bytes(40, 30)
    stored = list((upload_root / t).iterdir())
    assert sorted(p.suffix for p in stored) == [".jpg", ".png"]


def test_a_pdf_renamed_png_is_refused_and_nothing_is_stored(client: TestClient, upload_root: Path) -> None:
    t = thread(client)
    response = post(client, t, b"%PDF-1.7 not an image", "plan.png")
    assert response.status_code == 415
    assert response.json()["detail"]["failure_class"] == "unsupported_type"
    assert not (upload_root / t).exists() or list((upload_root / t).iterdir()) == []
    assert client.get(f"/chat/threads/{t}/uploads").json() == []


def test_an_oversized_image_is_refused_and_no_partial_file_remains(client: TestClient, upload_root: Path) -> None:
    t = thread(client)
    response = post(client, t, png_bytes(40, 30) + b"\x00" * 30_000)
    assert response.status_code == 413
    assert response.json()["detail"]["failure_class"] == "too_large"
    assert list((upload_root / t).iterdir()) == []
    assert client.get(f"/chat/threads/{t}/uploads").json() == []


def test_the_per_thread_count_is_enforced(client: TestClient) -> None:
    t = thread(client)
    for _ in range(3):
        assert post(client, t, png_bytes(8, 8)).status_code == 201
    assert post(client, t, png_bytes(8, 8)).status_code == 409


def test_an_unknown_thread_or_upload_is_not_found(client: TestClient) -> None:
    assert post(client, str(uuid4()), png_bytes(8, 8)).status_code == 404
    assert client.get(f"/chat/threads/{uuid4()}/uploads").status_code == 404
    assert client.get(f"/uploads/{uuid4()}").status_code == 404


def test_every_upload_route_needs_the_session(client: TestClient) -> None:
    anonymous = TestClient(client.app)
    t = thread(client)
    assert anonymous.post(f"/chat/threads/{t}/uploads", files={"file": ("a.png", png_bytes(8, 8))}).status_code == 401
    assert anonymous.get(f"/chat/threads/{t}/uploads").status_code == 401
    assert anonymous.get(f"/uploads/{uuid4()}").status_code == 401


def test_the_file_name_never_becomes_a_path(client: TestClient, upload_root: Path) -> None:
    t = thread(client)
    response = post(client, t, png_bytes(8, 8), "../../etc/passwd.png")
    assert response.status_code == 201
    assert response.json()["original_name"] == "../../etc/passwd.png"
    files = list((upload_root / t).iterdir())
    assert len(files) == 1 and files[0].name.endswith(".png") and "etc" not in files[0].name


def test_a_turn_naming_another_threads_upload_is_refused_naming_the_id(client: TestClient) -> None:
    from tests.graph_helpers import fake_models
    from tests.test_chat_api import install

    install(client, fake_models())
    mine, other = thread(client), thread(client)
    foreign = post(client, other, png_bytes(8, 8)).json()["upload_id"]
    response = client.post(f"/chat/threads/{mine}/turns", json={"message": "hi", "upload_ids": [foreign]})
    assert response.status_code == 422
    assert response.json()["detail"]["failure_class"] == "unknown_upload"
    assert foreign in response.json()["detail"]["reason"]
    assert client.get(f"/chat/threads/{mine}").json()["messages"] == []


def test_a_turn_takes_at_most_the_configured_images(client: TestClient) -> None:
    from tests.graph_helpers import fake_models
    from tests.test_chat_api import install

    install(client, fake_models())
    client.app.state.settings.turn_max_images = 1
    t = thread(client)
    ids = [post(client, t, png_bytes(8, 8)).json()["upload_id"] for _ in range(2)]
    response = client.post(f"/chat/threads/{t}/turns", json={"message": "hi", "upload_ids": ids})
    assert response.status_code == 422
    assert response.json()["detail"]["failure_class"] == "too_many_images"
