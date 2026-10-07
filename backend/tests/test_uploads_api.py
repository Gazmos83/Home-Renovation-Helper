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
    # A real PDF header: the second line is the binary marker every PDF writer adds.
    response = post(client, t, b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n", "plan.png")
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


# --- design files (design-import) ---------------------------------------------------


def design_bytes(**extra) -> bytes:
    import json as _json

    from app.design_import import load_template

    return _json.dumps({**load_template(), **extra}).encode("utf-8")


def test_a_design_file_is_accepted_stored_as_json_and_served_as_json(client: TestClient, upload_root: Path) -> None:
    t = thread(client)
    response = post(client, t, design_bytes(), "wall-unit.json")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "design" and body["original_name"] == "wall-unit.json"
    assert [p.suffix for p in (upload_root / t).iterdir()] == [".json"]
    fetched = client.get(f"/uploads/{body['upload_id']}")
    assert fetched.headers["content-type"] == "application/json"
    assert fetched.headers["x-content-type-options"] == "nosniff"
    assert fetched.content == design_bytes()
    assert [u["kind"] for u in client.get(f"/chat/threads/{t}/uploads").json()] == ["design"]


@pytest.mark.parametrize(
    "content",
    [b'["not", "a", "design"]', b'{"kind": "room_scene"}', b'{"kind": "custom_build"', b"\xff\xfe{}"],
    ids=["array", "room-scene", "broken-json", "not-utf8"],
)
def test_json_that_is_not_a_design_is_refused(client: TestClient, upload_root: Path, content: bytes) -> None:
    t = thread(client)
    response = post(client, t, content, "wall-unit.json")
    assert response.status_code == 415
    assert "design files" in response.json()["detail"]["reason"]
    assert not (upload_root / t).exists() or list((upload_root / t).iterdir()) == []


def test_an_oversized_design_is_refused_and_no_partial_file_remains(client: TestClient, upload_root: Path) -> None:
    client.app.state.settings.upload_max_design_bytes = 1024
    t = thread(client)
    response = post(client, t, design_bytes(), "wall-unit.json")
    assert response.status_code == 413
    assert "design file is larger than 1 KiB" in response.json()["detail"]["reason"]
    assert not (upload_root / t).exists() or list((upload_root / t).iterdir()) == []


def test_a_turn_takes_at_most_one_design_file(client: TestClient) -> None:
    from tests.graph_helpers import fake_models
    from tests.test_chat_api import install

    install(client, fake_models())
    client.app.state.settings.upload_max_per_thread = 5
    t = thread(client)
    ids = [post(client, t, design_bytes(), "wall-unit.json").json()["upload_id"] for _ in range(2)]
    response = client.post(f"/chat/threads/{t}/turns", json={"message": "import both", "upload_ids": ids})
    assert response.status_code == 422
    assert response.json()["detail"]["failure_class"] == "too_many_designs"


def test_a_design_does_not_count_towards_the_image_limit(client: TestClient) -> None:
    from tests.graph_helpers import fake_models
    from tests.test_chat_api import install

    install(client, fake_models(foreman={"decisions": [{"specialist": "intake", "reason": "t"}]}, intake={"replies": ["ok"]}))
    client.app.state.settings.turn_max_images = 1
    t = thread(client)
    ids = [post(client, t, png_bytes(8, 8)).json()["upload_id"], post(client, t, design_bytes(), "w.json").json()["upload_id"]]
    response = client.post(f"/chat/threads/{t}/turns", json={"message": "a photo and a design", "upload_ids": ids})
    assert response.status_code == 200, response.text


NOTE = "# Living room\n\n| Wall | Length |\n|---|---|\n| north | 4000 mm |\n\tCeiling 2450 mm — measured.\r\n".encode()


def test_a_markdown_note_is_accepted_stored_as_md_and_served_as_plain_text(
    client: TestClient, upload_root: Path
) -> None:
    t = thread(client)
    response = post(client, t, NOTE, "living-room.md")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "text" and body["original_name"] == "living-room.md"
    assert [p.suffix for p in (upload_root / t).iterdir()] == [".md"]
    fetched = client.get(f"/uploads/{body['upload_id']}")
    assert fetched.headers["content-type"] == "text/plain; charset=utf-8"
    assert fetched.headers["x-content-type-options"] == "nosniff"
    assert fetched.content == NOTE
    assert [u["kind"] for u in client.get(f"/chat/threads/{t}/uploads").json()] == ["text"]


@pytest.mark.parametrize(
    "content",
    [b"PK\x03\x04\x14\x00\x00\x00\x08\x00notes.md", b"plain text with a \x00 null", b"bell \x07 ring"],
    ids=["zip", "nul", "control"],
)
def test_binary_named_md_is_refused_and_nothing_is_stored(
    client: TestClient, upload_root: Path, content: bytes
) -> None:
    t = thread(client)
    response = post(client, t, content, "notes.md")
    assert response.status_code == 415
    assert response.json()["detail"]["failure_class"] == "unsupported_type"
    assert not (upload_root / t).exists() or list((upload_root / t).iterdir()) == []


def test_an_oversized_note_is_refused_and_no_partial_file_remains(client: TestClient, upload_root: Path) -> None:
    client.app.state.settings.upload_max_note_bytes = 1024
    t = thread(client)
    response = post(client, t, b"measurements " * 200, "living-room.md")
    assert response.status_code == 413
    assert "note is larger than 1 KiB" in response.json()["detail"]["reason"]
    assert not (upload_root / t).exists() or list((upload_root / t).iterdir()) == []


def test_a_note_far_over_every_cap_is_refused_as_a_note(client: TestClient, upload_root: Path) -> None:
    client.app.state.settings.upload_max_note_bytes = 1024
    client.app.state.settings.upload_max_design_bytes = 1024
    t = thread(client)
    # The checked prefix (cap + 1 bytes) ends inside the two-byte "ß", which must not read as binary.
    content = b"xx" + "Maße ".encode() * 600
    assert content[1024:1025] == b"\xc3"
    response = post(client, t, content, "living-room.md")
    assert response.status_code == 413
    assert "note is larger" in response.json()["detail"]["reason"]


def test_a_design_still_needs_its_kind_although_notes_are_text(client: TestClient) -> None:
    """Text that opens like JSON is a design file or nothing (design-import stays as it was)."""
    t = thread(client)
    assert post(client, t, b'  {"kind": "room_scene"}', "wall-unit.md").status_code == 415
    assert post(client, t, design_bytes(), "wall-unit.txt").json()["kind"] == "design"
