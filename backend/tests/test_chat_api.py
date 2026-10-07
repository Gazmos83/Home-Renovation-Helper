"""homeowner-chat: the owner-gated chat routes against the test database and the real checkpointer."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import httpx2
import openai
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.foreman import build_graph
from app.agent.tools.base import ToolDeps
from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch
from tests.conftest import clean_house_file
from tests.fakes import tool_call
from tests.graph_helpers import fake_models

HALL = {
    "room_name": "Hall",
    "corners_mm": [[0, 0], [1200, 0], [1200, 3000], [0, 3000]],
    "ceiling_height_mm": 2400,
    "purpose": "a bench by the front door",
    "budget_eur": 400,
}


def install(client: TestClient, models) -> None:
    app = client.app
    app.state.graph = build_graph(
        app.state.engine,
        app.state.settings,
        model_provider=models.__getitem__,
        model_ids=app.state.routing.model_for,
        checkpointer=app.state.checkpointer,
        deps=ToolDeps(app.state),
    )


def brief_models(*decisions: str):
    return fake_models(
        foreman={"decisions": [{"specialist": d, "reason": "t"} for d in (decisions or ("intake",))]},
        intake={"steps": [[tool_call("record_brief", HALL)], "Saved. Shall I design it?"]},
    )


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    clean_house_file(c.app.state.engine)
    sign_in(c)
    yield c
    clean_house_file(c.app.state.engine)
    c.__exit__(None, None, None)


def start(client: TestClient, **body) -> str:
    response = client.post("/chat/threads", json=body)
    assert response.status_code == 201, response.text
    return response.json()["thread_id"]


def test_every_route_needs_the_session(client: TestClient) -> None:
    anonymous = TestClient(client.app)
    thread = str(uuid4())
    for method, path, body in (
        ("post", "/chat/threads", {}),
        ("get", "/chat/threads", None),
        ("get", f"/chat/threads/{thread}", None),
        ("post", f"/chat/threads/{thread}/turns", {"message": "hi"}),
        ("post", f"/chat/threads/{thread}/resume", {"confirmation_id": "x", "answer": "yes"}),
    ):
        response = getattr(anonymous, method)(path, **({"json": body} if body is not None else {}))
        assert response.status_code == 401, path


def test_start_list_turn_and_read(client: TestClient) -> None:
    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}]},
        intake={"replies": ["How wide is the hall?"]},
    ))
    thread = start(client, title="Hall bench")
    assert thread in [t["thread_id"] for t in client.get("/chat/threads").json()]

    turn = client.post(f"/chat/threads/{thread}/turns", json={"message": "a bench for the hall"})
    assert turn.status_code == 200, turn.text
    assert turn.json() == {"reply": "How wide is the hall?", "specialist": "intake", "pending": None}

    read = client.get(f"/chat/threads/{thread}").json()
    assert read["title"] == "Hall bench"
    assert read["messages"] == [
        {"role": "owner", "text": "a bench for the hall"},
        {"role": "assistant", "text": "How wide is the hall?"},
    ]
    assert read["pending"] is None


def test_a_thread_for_a_package_that_does_not_exist_is_refused(client: TestClient) -> None:
    response = client.post("/chat/threads", json={"package_id": "ghost"})
    assert response.status_code == 422
    assert response.json()["detail"]["failure_class"] == "unknown_package"


def test_an_unknown_thread_is_not_found(client: TestClient) -> None:
    install(client, fake_models())
    assert client.get(f"/chat/threads/{uuid4()}").status_code == 404
    assert client.post(f"/chat/threads/{uuid4()}/turns", json={"message": "hi"}).status_code == 404


def test_a_confirmation_answered_yes_runs_the_action(client: TestClient) -> None:
    install(client, brief_models())
    thread = start(client)
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench, 1200 wide"}).json()
    assert paused["specialist"] == "intake"
    assert paused["pending"]["subject"] == "brief"
    assert "Room Hall: 1200 × 3000 mm" in paused["pending"]["summary"]

    shown = client.get(f"/chat/threads/{thread}").json()
    assert shown["pending"]["confirmation_id"] == paused["pending"]["confirmation_id"]

    done = client.post(
        f"/chat/threads/{thread}/resume",
        json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["reply"] == "Saved. Shall I design it?"
    assert done.json()["pending"] is None
    with Session(client.app.state.engine) as session:
        assert house_file.room_by_name(session, "Hall") is not None


def test_a_confirmation_answered_no_writes_nothing(client: TestClient) -> None:
    install(client, brief_models())
    thread = start(client)
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"}).json()
    declined = client.post(
        f"/chat/threads/{thread}/resume",
        json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "no", "reason": "too much"},
    )
    assert declined.status_code == 200
    with Session(client.app.state.engine) as session:
        assert house_file.room_by_name(session, "Hall") is None


def test_a_message_while_a_confirmation_is_pending_is_refused_naming_the_subject(client: TestClient) -> None:
    install(client, brief_models())
    thread = start(client)
    client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"})
    again = client.post(f"/chat/threads/{thread}/turns", json={"message": "and a shelf"})
    assert again.status_code == 409
    assert "brief" in again.json()["detail"]["reason"]


def test_a_stale_or_unknown_confirmation_id_is_refused_and_nothing_runs(client: TestClient) -> None:
    install(client, brief_models())
    thread = start(client)
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"}).json()

    wrong = client.post(f"/chat/threads/{thread}/resume", json={"confirmation_id": "nope", "answer": "yes"})
    assert wrong.status_code == 409
    with Session(client.app.state.engine) as session:
        assert house_file.room_by_name(session, "Hall") is None

    right = {"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"}
    assert client.post(f"/chat/threads/{thread}/resume", json=right).status_code == 200
    stale = client.post(f"/chat/threads/{thread}/resume", json=right)
    assert stale.status_code == 409
    assert stale.json()["detail"]["failure_class"] == "no_such_confirmation"


def test_an_answer_other_than_yes_or_no_is_refused(client: TestClient) -> None:
    install(client, brief_models())
    thread = start(client)
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"}).json()
    response = client.post(
        f"/chat/threads/{thread}/resume",
        json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "maybe"},
    )
    assert response.status_code == 422


def test_without_the_checkpointer_a_turn_is_refused_with_the_memory_reason(client: TestClient) -> None:
    thread = start(client)
    client.app.state.graph = None
    response = client.post(f"/chat/threads/{thread}/turns", json={"message": "hello"})
    assert response.status_code == 503
    assert "conversation memory is not available" in response.json()["detail"]["reason"]


def test_a_gateway_timeout_is_reported_with_its_class(client: TestClient) -> None:
    timeout = openai.APITimeoutError(request=httpx2.Request("POST", "https://openrouter.ai/x"))
    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}]}, intake={"error": timeout},
    ))
    thread = start(client)
    response = client.post(f"/chat/threads/{thread}/turns", json={"message": "a bench"})
    assert response.status_code == 502
    assert response.json()["detail"]["failure_class"] == "timeout"
    assert client.get(f"/chat/threads/{thread}").json()["messages"] == []


def test_no_response_shows_a_model_a_token_count_or_a_host_path(client: TestClient, render_root: Path) -> None:
    install(client, brief_models())
    thread = start(client)
    bodies = []
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"})
    bodies.append(paused.text)
    bodies.append(client.get(f"/chat/threads/{thread}").text)
    done = client.post(
        f"/chat/threads/{thread}/resume",
        json={"confirmation_id": paused.json()["pending"]["confirmation_id"], "answer": "yes"},
    )
    bodies.append(done.text)
    bodies.append(client.get("/chat/threads").text)
    everything = json.dumps(bodies).lower()

    slugs = [slug for _slot, slug in client.app.state.routing.items()]
    for slug in slugs:
        assert slug.lower() not in everything
    for word in ("deepseek", "gpt-", "tokens", "token_count", "cost", "/home/", str(render_root).lower()):
        assert word not in everything


def test_a_piece_created_through_chat_is_built_on_the_apps_loop(client: TestClient, render_root: Path) -> None:
    from app.blender import storage
    from tests.api_helpers import desk
    from tests.conftest import wait_for_status

    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}, {"specialist": "designer", "reason": "t"}]},
        intake={"steps": [[tool_call("record_brief", HALL)], "Saved."]},
        designer={"steps": [[tool_call("create_piece", {"package_id": "hall-bench", "spec": desk()})], "Created."]},
    ))
    thread = start(client)
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"}).json()
    client.post(
        f"/chat/threads/{thread}/resume",
        json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"},
    )
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "design it"}).json()
    assert paused["pending"]["subject"] == "create_piece"
    assert storage.versions(render_root, "hall-bench") == []
    done = client.post(
        f"/chat/threads/{thread}/resume",
        json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"},
    )
    assert done.status_code == 200, done.text
    wait_for_status(storage.version_dir(render_root, "hall-bench", 1))
    assert client.get(f"/chat/threads/{thread}").json()["package_id"] == "hall-bench"


def _shelves() -> int:
    from tests.api_helpers import desk

    cabinet = next(m for m in desk()["modules"] if m["id"] == "cabinet")
    return cabinet["shelves"]


def _revise_models(package_id: str):
    return fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}, {"specialist": "designer", "reason": "t"}]},
        intake={"steps": [[tool_call("record_brief", HALL)], "Saved."]},
        designer={"steps": [
            [tool_call("revise_package", {
                "package_id": package_id,
                "changes": {"modules": {"cabinet": {"shelves": _shelves() + 1}}},
            })],
            "Revised.",
        ]},
    )


def _piece_of(client: TestClient, thread: str) -> str | None:
    listed = {t["thread_id"]: t for t in client.get("/chat/threads").json()}
    assert listed[thread]["package_id"] == client.get(f"/chat/threads/{thread}").json()["package_id"]
    return listed[thread]["package_id"]


def test_a_confirmed_revision_binds_an_unbound_thread(client: TestClient, render_root: Path) -> None:
    from app.blender import storage
    from tests.api_helpers import create
    from tests.conftest import wait_for_status

    assert create(client).status_code == 202
    wait_for_status(storage.version_dir(render_root, "hall-bench", 1))
    install(client, _revise_models("hall-bench"))
    thread = start(client)
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"}).json()
    client.post(f"/chat/threads/{thread}/resume",
                json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"})
    assert _piece_of(client, thread) is None
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "one more shelf"}).json()
    assert paused["pending"], paused
    assert paused["pending"]["subject"] == "revise"
    assert _piece_of(client, thread) is None
    client.post(
        f"/chat/threads/{thread}/resume",
        json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"},
    )
    assert _piece_of(client, thread) == "hall-bench"


def test_a_second_created_piece_rebinds_the_thread(client: TestClient, render_root: Path) -> None:
    from tests.api_helpers import desk

    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}] + [{"specialist": "designer", "reason": "t"}] * 2},
        intake={"steps": [[tool_call("record_brief", HALL)], "Saved."]},
        designer={"steps": [
            [tool_call("create_piece", {"package_id": "hall-bench", "spec": desk()})], "Created.",
            [tool_call("create_piece", {"package_id": "hall-shelf", "spec": desk()})], "Created.",
        ]},
    ))
    thread = start(client)
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"}).json()
    client.post(f"/chat/threads/{thread}/resume",
                json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"})
    for name in ("hall-bench", "hall-shelf"):
        paused = client.post(f"/chat/threads/{thread}/turns", json={"message": f"design {name}"}).json()
        client.post(f"/chat/threads/{thread}/resume",
                    json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"})
        assert _piece_of(client, thread) == name


def test_a_declined_piece_leaves_the_thread_unbound(client: TestClient, render_root: Path) -> None:
    from tests.api_helpers import desk

    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}, {"specialist": "designer", "reason": "t"}]},
        intake={"steps": [[tool_call("record_brief", HALL)], "Saved."]},
        designer={"steps": [[tool_call("create_piece", {"package_id": "hall-bench", "spec": desk()})], "Declined."]},
    ))
    thread = start(client)
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"}).json()
    client.post(f"/chat/threads/{thread}/resume",
                json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"})
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "design it"}).json()
    client.post(f"/chat/threads/{thread}/resume",
                json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "no", "reason": "no"})
    assert _piece_of(client, thread) is None


def test_progress_needs_the_session_and_a_known_thread(client: TestClient) -> None:
    install(client, fake_models())
    assert TestClient(client.app).get(f"/chat/threads/{uuid4()}/progress").status_code == 401
    assert client.get(f"/chat/threads/{uuid4()}/progress").status_code == 404


def test_progress_without_the_checkpointer_is_refused_with_the_memory_reason(client: TestClient) -> None:
    thread = start(client)
    client.app.state.graph = None
    response = client.get(f"/chat/threads/{thread}/progress")
    assert response.status_code == 503
    assert "conversation memory is not available" in response.json()["detail"]["reason"]


def test_a_fresh_thread_reports_no_piece_and_asks_for_a_description(client: TestClient) -> None:
    install(client, fake_models())
    thread = start(client)
    body = client.get(f"/chat/threads/{thread}/progress").json()
    assert body["package_id"] is None
    assert not any(step["done"] for step in body["steps"])
    assert body["next_step"] == "Describe the piece you want"


def test_a_built_and_reviewed_piece_shows_in_the_progress(client: TestClient, render_root: Path) -> None:
    from app.blender import storage
    from tests.api_helpers import create
    from tests.conftest import wait_for_status

    assert create(client).status_code == 202
    folder = storage.version_dir(render_root, "hall-bench", 1)
    wait_for_status(folder)
    (folder / "screenshot.png").write_bytes(b"png")
    storage.write_render_status(folder, "turntable", status="succeeded", tier="draft")
    with Session(client.app.state.engine) as session:
        house_file.record_piece(session, "hall-bench", "Hall bench")
        house_file.record_version(session, "hall-bench", 1)
        house_file.record_review(session, "hall-bench", 1, ["screenshot.png"], [
            {"aspect": "brief", "expected": "a", "expected_source": "brief", "observed": "b", "image": 1, "severity": "minor"},
            {"aspect": "render", "expected": "a", "expected_source": "brief", "observed": "b", "image": 1, "severity": "minor"},
        ])
        session.commit()
    install(client, fake_models())
    thread = start(client, package_id="hall-bench")
    body = client.get(f"/chat/threads/{thread}/progress").json()
    done = {s["step"]: s for s in body["steps"]}
    assert body["latest_version"] == 1
    assert done["built"]["done"] and done["rendered"]["done"] and done["reviewed"]["done"]
    assert not done["detail"]["done"] and not done["final"]["done"]
    assert done["reviewed"]["detail"] == "2 open"
    assert body["open_review_items"] == 2
    assert body["screenshot"] == "/packages/hall-bench/versions/1/files/screenshot.png"
    text = json.dumps(body).lower()
    for word in ("deepseek", "gpt-", "token", "cost", "/home/", str(render_root).lower()):
        assert word not in text
