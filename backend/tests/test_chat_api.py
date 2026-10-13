"""homeowner-chat: the owner-gated chat routes against the test database and the real checkpointer."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx2
import openai
import pytest
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.foreman import build_graph
from app.agent.tools.base import ToolDeps
from tests.api_helpers import confirm_thread_room, make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch
from tests.conftest import clean_house_file
from tests.fakes import FakeChatModel, tool_call
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


def without_ids(messages: list[dict]) -> list[dict]:
    """The history as shown, without the owner messages' ids (random per run)."""
    return [{key: value for key, value in m.items() if key != "message_id"} for m in messages]


def start(client: TestClient, room: str | None = "Studio", **body) -> str:
    """A new conversation that has already confirmed `room` (`None`: a brand-new one)."""
    response = client.post("/chat/threads", json=body)
    assert response.status_code == 201, response.text
    thread = response.json()["thread_id"]
    if room:
        confirm_thread_room(client, thread, room)
    return thread


def test_every_route_needs_the_session(client: TestClient) -> None:
    anonymous = TestClient(client.app)
    thread = str(uuid4())
    for method, path, body in (
        ("post", "/chat/threads", {}),
        ("get", "/chat/threads", None),
        ("get", f"/chat/threads/{thread}", None),
        ("post", f"/chat/threads/{thread}/turns", {"message": "hi"}),
        ("post", f"/chat/threads/{thread}/resume", {"confirmation_id": "x", "answer": "yes"}),
        ("delete", f"/chat/threads/{thread}", None),
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
    assert without_ids(read["messages"]) == [
        {"role": "owner", "text": "a bench for the hall"},
        {"role": "assistant", "text": "How wide is the hall?"},
    ]
    assert read["pending"] is None


def test_a_thread_for_a_package_that_does_not_exist_is_refused(client: TestClient) -> None:
    response = client.post("/chat/threads", json={"package_id": "ghost"})
    assert response.status_code == 422
    assert response.json()["detail"]["failure_class"] == "unknown_package"


def test_starting_a_thread_for_a_piece_binds_it_and_a_second_start_is_refused(
    client: TestClient,
) -> None:
    from tests.api_helpers import create

    create(client, "hall-bench")
    first = client.post("/chat/threads", json={"package_id": "hall-bench"})
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["package_id"] == "hall-bench"
    thread_id = body["thread_id"]

    with Session(client.app.state.engine) as session:
        builds = house_file.builds_of(session, UUID(thread_id))
        assert [b.package_id for b in builds] == ["hall-bench"]

    again = client.post("/chat/threads", json={"package_id": "hall-bench"})
    assert again.status_code == 409, again.text
    detail = again.json()["detail"]
    assert detail["failure_class"] == "piece_has_conversation"
    assert "hall-bench" in detail["reason"]
    assert len(client.get("/chat/threads").json()) == 1


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
    bodies.append(client.get(f"/chat/threads/{thread}").text)
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


def test_a_second_created_piece_is_refused_and_the_thread_stays_bound(
    client: TestClient, render_root: Path
) -> None:
    from app.blender import storage
    from tests.api_helpers import desk

    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}] + [{"specialist": "designer", "reason": "t"}] * 2},
        intake={"steps": [[tool_call("record_brief", HALL)], "Saved."]},
        designer={"steps": [
            [tool_call("create_piece", {"package_id": "hall-bench", "spec": desk()})], "Created.",
            [tool_call("create_piece", {"package_id": "hall-shelf", "spec": desk()})], "Could not.",
        ]},
    ))
    thread = start(client)
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"}).json()
    client.post(f"/chat/threads/{thread}/resume",
                json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"})
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "design hall-bench"}).json()
    client.post(f"/chat/threads/{thread}/resume",
                json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"})
    assert _piece_of(client, thread) == "hall-bench"
    second = client.post(f"/chat/threads/{thread}/turns", json={"message": "design hall-shelf"}).json()
    # No confirmation: create_piece refused because the conversation is already bound.
    assert second.get("pending") is None
    assert _piece_of(client, thread) == "hall-bench"
    assert storage.versions(render_root, "hall-shelf") == []


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
    assert (body["version_count"], body["max_versions"]) == (1, 15)
    assert body["approved_version"] is None
    assert done["built"]["done"] and done["rendered"]["done"] and done["reviewed"]["done"]
    assert not done["detail"]["done"] and not done["final"]["done"]
    assert done["reviewed"]["detail"] == "2 open"
    assert body["open_review_items"] == 2
    assert body["screenshot"] == "/packages/hall-bench/versions/1/files/screenshot.png"
    assert body["viewer"] is None  # the status says succeeded, but no frames or viewer were written
    text = json.dumps(body).lower()
    for word in ("deepseek", "gpt-", "token", "cost", "/home/", str(render_root).lower()):
        assert word not in text

    with Session(client.app.state.engine) as session:
        house_file.approve_version(session, "hall-bench", 1)
        session.commit()
    body = client.get(f"/chat/threads/{thread}/progress").json()
    assert body["approved_version"] == 1

    (folder / "frames").mkdir(exist_ok=True)
    (folder / "frames" / "frame_000.png").write_bytes(b"png")
    (folder / "viewer.html").write_text("<html></html>")
    body = client.get(f"/chat/threads/{thread}/progress").json()
    assert body["viewer"] == "/packages/hall-bench/versions/1/files/viewer.html"


def test_progress_names_the_threads_own_room_and_its_3d_view(client: TestClient, render_root: Path) -> None:
    from app.blender import storage

    install(client, fake_models())
    thread = start(client, room="Hall")
    other = start(client, room=None)
    with Session(client.app.state.engine) as session:
        house_file.record_piece(session, "hall-bench", "Hall bench")
        house_file.set_piece_room(session, "hall-bench", house_file.room_by_name(session, "Hall"))
        composition = house_file.record_composition(session, "room", "Hall")
        house_file.record_composition_version(session, composition, 1, None, [])
        session.commit()
        slug = composition.slug
    folder = storage.composition_version_dir(render_root, slug, 1)
    folder.mkdir(parents=True)
    (folder / "model.glb").write_bytes(b"glb")
    (folder / "report.json").write_text("{}", encoding="utf-8")

    body = client.get(f"/chat/threads/{thread}/progress").json()
    room = body["room"]
    assert {key: room[key] for key in ("name", "scope", "slug", "model", "surfaces")} == {
        "name": "Hall",
        "scope": "room",
        "slug": slug,
        "model": f"/compositions/{slug}/versions/1/files/model.glb",
        "surfaces": f"/compositions/{slug}/versions/1/files/report.json",
    }
    [only] = room["versions"]
    assert (only["version"], only["dimensions"]) == (1, f"/compositions/{slug}/versions/1/dimensions")
    assert room["approved_version"] is None and only["approved_at"] is None
    assert room["approved_picture"] is None
    assert str(render_root) not in json.dumps(body)

    with Session(client.app.state.engine) as session:
        house_file.approve_composition_version(session, render_root, slug, 1)
        session.commit()
    room = client.get(f"/chat/threads/{thread}/progress").json()["room"]
    assert room["approved_version"] == 1
    assert room["versions"][0]["approved_at"] is not None
    assert room["approved_picture"] is None  # approved, but nothing was rendered yet
    (folder / "screenshot.png").write_bytes(b"png")
    room = client.get(f"/chat/threads/{thread}/progress").json()["room"]
    assert room["approved_picture"] == f"/compositions/{slug}/versions/1/files/screenshot.png"

    # Another conversation sees neither this one's room nor the room its piece is in.
    with Session(client.app.state.engine) as session:
        house_file.set_active_build(session, UUID(other), "hall-bench")
        session.commit()
    assert client.get(f"/chat/threads/{other}/progress").json()["room"] is None


# --- history (foreman-routing-fixes) ----------------------------------------------


def _history_of(messages) -> list[dict[str, str]]:
    from types import SimpleNamespace

    from app.agent import chat

    graph = SimpleNamespace(
        get_state=lambda _config, **_kw: SimpleNamespace(values={"messages": messages}, interrupts=())
    )
    return chat.history(graph, thread_id=uuid4(), owner_id=uuid4())


def test_a_reply_sent_with_a_tool_call_is_shown_without_the_call() -> None:
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    call = {"id": "c1", "name": "create_piece", "args": {"package_id": "wall", "spec": {"secret": "args"}}}
    shown = _history_of([
        HumanMessage("design it"),
        AIMessage("Here's how your spec forces the dimensions.", tool_calls=[call]),
        ToolMessage("Created wall version 1.", tool_call_id="c1"),
        AIMessage("\n\n", tool_calls=[{**call, "id": "c2"}]),
        ToolMessage("Created.", tool_call_id="c2"),
        AIMessage("It is building."),
    ])
    assert shown == [
        {"role": "owner", "text": "design it"},
        {"role": "assistant", "text": "Here's how your spec forces the dimensions."},
        {"role": "assistant", "text": "It is building."},
    ]
    assert "secret" not in json.dumps(shown) and "Created" not in json.dumps(shown)


def test_an_owner_message_names_the_files_sent_with_it() -> None:
    from langchain_core.messages import AIMessage, HumanMessage

    shown = _history_of([
        HumanMessage("this is my flat", additional_kwargs={"upload_ids": ["u1", "u2"]}),
        AIMessage("I can see the plan."),
        HumanMessage("thanks"),
    ])
    assert shown == [
        {"role": "owner", "text": "this is my flat", "upload_ids": ["u1", "u2"]},
        {"role": "assistant", "text": "I can see the plan."},
        {"role": "owner", "text": "thanks"},
    ]


def test_an_answered_confirmation_is_one_line_before_the_reply_that_followed(client: TestClient) -> None:
    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}]},
        intake={"steps": [[tool_call("record_brief", HALL)], "Four shelves, then? Tell me the change."]},
    ))
    thread = start(client)
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"}).json()
    pending = paused["pending"]
    read = client.get(f"/chat/threads/{thread}").json()
    assert [m["role"] for m in read["messages"]] == ["owner"]
    assert read["pending"]["confirmation_id"] == pending["confirmation_id"]

    client.post(
        f"/chat/threads/{thread}/resume",
        json={"confirmation_id": pending["confirmation_id"], "answer": "no", "reason": "make it 4 shelves"},
    )
    messages = client.get(f"/chat/threads/{thread}").json()["messages"]
    assert without_ids(messages) == [
        {"role": "owner", "text": "a hall bench"},
        {"role": "confirmation", "text": f"brief: {pending['summary']} — no (make it 4 shelves)"},
        {"role": "assistant", "text": "Four shelves, then? Tell me the change."},
    ]


def test_the_words_sent_with_a_gated_call_show_above_the_pending_card(client: TestClient) -> None:
    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}]},
        intake={"steps": [("Your hall is 1200 by 3000, so here is the brief.", [tool_call("record_brief", HALL)]), "Saved."]},
    ))
    thread = start(client)
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"}).json()
    read = client.get(f"/chat/threads/{thread}").json()
    assert without_ids(read["messages"]) == [
        {"role": "owner", "text": "a hall bench"},
        {"role": "assistant", "text": "Your hall is 1200 by 3000, so here is the brief."},
    ]
    assert read["pending"]["confirmation_id"] == paused["pending"]["confirmation_id"]

    client.post(f"/chat/threads/{thread}/resume", json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"})
    after = client.get(f"/chat/threads/{thread}").json()["messages"]
    assert [m["role"] for m in after] == ["owner", "assistant", "confirmation", "assistant"]
    assert after[1]["text"] == "Your hall is 1200 by 3000, so here is the brief."


# --- deleting a conversation (piece-versions-and-chat-delete) --------------------------------------


def _conversation_with_a_piece_and_uploads(client: TestClient, tmp_path: Path) -> tuple[str, list[str]]:
    from app.blender import storage
    from tests.blender_fakes import png_bytes

    client.app.state.settings.upload_root = tmp_path / "uploads"
    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}]},
        intake={"replies": ["Noted."]},
    ))
    thread = start(client, title="Murphy bed")
    assert client.post(f"/chat/threads/{thread}/turns", json={"message": "hello"}).status_code == 200
    uploaded = [
        client.post(f"/chat/threads/{thread}/uploads", files={"file": (f"p{n}.png", png_bytes(8, 8), "image/png")})
        .json()["upload_id"]
        for n in (1, 2)
    ]
    root = client.app.state.settings.render_root
    with Session(client.app.state.engine) as session:
        house_file.record_piece(session, "murphy-bed", "Murphy bed")
        for version in (1, 2):
            folder = storage.version_dir(root, "murphy-bed", version)
            folder.mkdir(parents=True)
            (folder / storage.INPUT_FILE).write_text("{}", encoding="utf-8")
            house_file.record_version(session, "murphy-bed", version)
        house_file.touch_thread(session, thread, package_id="murphy-bed")
        session.commit()
    return thread, uploaded


def test_deleting_a_conversation_removes_its_memory_index_and_uploads_and_keeps_the_piece(
    client: TestClient, tmp_path: Path
) -> None:
    thread, uploaded = _conversation_with_a_piece_and_uploads(client, tmp_path)
    upload_dir = tmp_path / "uploads" / thread
    assert len(list(upload_dir.iterdir())) == 2

    response = client.delete(f"/chat/threads/{thread}")
    assert response.status_code == 204

    assert client.get(f"/chat/threads/{thread}").status_code == 404
    assert thread not in [t["thread_id"] for t in client.get("/chat/threads").json()]
    for upload_id in uploaded:
        assert client.get(f"/uploads/{upload_id}").status_code == 404
    assert not upload_dir.exists()
    memory = client.app.state.checkpointer.get_tuple({"configurable": {"thread_id": f"chat:{thread}", "checkpoint_ns": ""}})
    assert memory is None
    listed = {p["package_id"]: p for p in client.get("/packages").json()}
    assert listed["murphy-bed"]["versions"] == [2, 1]
    assert listed["murphy-bed"]["room"] is None
    assert listed["murphy-bed"]["thread_id"] is None
    with Session(client.app.state.engine) as session:
        piece = {p["package_id"]: p for p in house_file.pieces(session, client.app.state.settings.render_root)}
    assert [v["version"] for v in piece["murphy-bed"]["versions"]] == [1, 2]


def test_a_conversation_with_a_running_turn_is_not_deleted(client: TestClient, tmp_path: Path) -> None:
    from uuid import UUID

    from app.api import chat as chat_api

    thread, _ = _conversation_with_a_piece_and_uploads(client, tmp_path)
    chat_api._running.add(UUID(thread))
    try:
        response = client.delete(f"/chat/threads/{thread}")
    finally:
        chat_api._running.discard(UUID(thread))
    assert response.status_code == 409
    assert response.json()["detail"] == {"failure_class": "turn_running", "reason": chat_api.TURN_RUNNING}
    assert client.get(f"/chat/threads/{thread}").status_code == 200


def test_a_memory_failure_deletes_nothing(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    from app.agent import chat as chat_module

    thread, uploaded = _conversation_with_a_piece_and_uploads(client, tmp_path)

    def broken(graph, thread_id) -> None:
        raise RuntimeError("database down")

    monkeypatch.setattr(chat_module, "forget", broken)
    response = client.delete(f"/chat/threads/{thread}")
    assert response.status_code == 503
    assert response.json()["detail"]["failure_class"] == "unavailable"
    assert client.get(f"/chat/threads/{thread}").status_code == 200
    assert client.get(f"/uploads/{uploaded[0]}").status_code == 200


def test_deleting_an_unknown_conversation_is_not_found(client: TestClient) -> None:
    install(client, fake_models())
    assert client.delete(f"/chat/threads/{uuid4()}").status_code == 404


def test_the_running_mark_is_cleared_after_a_turn_that_fails(client: TestClient) -> None:
    from app.api import chat as chat_api

    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}]},
        intake={"error": RuntimeError("boom")},
    ))
    thread = start(client)
    with pytest.raises(RuntimeError):
        client.post(f"/chat/threads/{thread}/turns", json={"message": "hello"})
    assert chat_api._running == set()



# --- streamed turns (studio-chat-polish) -------------------------------------------


def events_of(response) -> list[tuple[str, dict]]:
    """The Server-Sent Events of a streamed response, in order.

    SSE comment keepalives (`: …`) are skipped; they are not named events.
    """
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in response.text.split("\n\n"):
        if not block.strip() or block.lstrip().startswith(":"):
            continue
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def _built_bench(client: TestClient, render_root: Path) -> None:
    from app.blender import storage
    from tests.api_helpers import create
    from tests.conftest import wait_for_status

    assert create(client).status_code == 202
    wait_for_status(storage.version_dir(render_root, "hall-bench", 1))


def _designer_revises():
    return fake_models(
        foreman={"decisions": [{"specialist": "designer", "reason": "t"}]},
        designer={"steps": [
            [tool_call("revise_package", {
                "package_id": "hall-bench",
                "changes": {"modules": {"cabinet": {"shelves": _shelves() + 1}}},
            })],
            "Revised.",
        ]},
    )


def test_a_quiet_stream_sends_keepalive_comments(client: TestClient, monkeypatch) -> None:
    """Comment frames keep the SSE socket alive while the specialist is still thinking."""
    import time

    from app.api import chat as chat_api

    monkeypatch.setattr(chat_api, "_SSE_KEEPALIVE_SECONDS", 0.05)
    install(
        client,
        fake_models(
            foreman={"decisions": [{"specialist": "intake", "reason": "t"}]},
            intake={"replies": ["ok"], "delay": 0.2},
        ),
    )
    # FakeChatModel may not honour delay; slow the work queue by patching _events.
    real_events = chat_api._events

    def slow_events(*args, **kwargs):
        time.sleep(0.18)
        yield from real_events(*args, **kwargs)

    monkeypatch.setattr(chat_api, "_events", slow_events)
    thread = start(client, title="Hall")
    response = client.post(f"/chat/threads/{thread}/turns/stream", json={"message": "hello"})
    assert response.status_code == 200
    assert ": keepalive" in response.text
    kinds = [kind for kind, _ in events_of(response)]
    assert "done" in kinds


def test_a_streamed_turn_reports_the_designer_its_tool_and_the_pause(client: TestClient, render_root: Path) -> None:
    _built_bench(client, render_root)
    install(client, _designer_revises())
    thread = start(client, title="Hall bench", package_id="hall-bench")

    response = client.post(f"/chat/threads/{thread}/turns/stream", json={"message": "one more shelf"})
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    events = events_of(response)
    assert [kind for kind, _ in events] == ["specialist", "tool", "pending", "done"]
    assert events[0][1] == {"role": "designer"}
    assert events[1][1] == {"plugin": "revise package"}
    pending = events[2][1]["pending"]
    assert pending["subject"] == "revise"

    resumed = events_of(client.post(
        f"/chat/threads/{thread}/resume/stream",
        json={"confirmation_id": pending["confirmation_id"], "answer": "no", "reason": "keep it"},
    ))
    assert [kind for kind, _ in resumed] == ["tool", "reply", "done"]
    assert resumed[1][1] == {"reply": "Revised.", "specialists": ["designer"]}
    assert client.get(f"/chat/threads/{thread}").json()["pending"] is None


def test_no_internals_reach_a_streamed_event(client: TestClient, render_root: Path) -> None:
    _built_bench(client, render_root)
    install(client, _designer_revises())
    thread = start(client, title="Hall bench", package_id="hall-bench")
    first = client.post(f"/chat/threads/{thread}/turns/stream", json={"message": "one more shelf"})
    pending = events_of(first)[2][1]["pending"]
    second = client.post(
        f"/chat/threads/{thread}/resume/stream",
        json={"confirmation_id": pending["confirmation_id"], "answer": "yes"},
    )
    routing = client.app.state.routing
    for response in (first, second):
        for kind, data in events_of(response):
            body = json.dumps(data)
            for slug in routing.distinct_slugs():
                assert slug not in body
            assert "token" not in body.lower()
            assert str(render_root) not in body and str(client.app.state.settings.upload_root) not in body
            if kind == "tool":
                assert set(data) == {"plugin"}  # never the tool's arguments
            if kind == "specialist":
                assert set(data) == {"role"}


def test_refusals_before_the_turn_open_no_stream(client: TestClient, render_root: Path) -> None:
    _built_bench(client, render_root)
    install(client, _designer_revises())
    thread = start(client, title="Hall bench", package_id="hall-bench")
    events_of(client.post(f"/chat/threads/{thread}/turns/stream", json={"message": "one more shelf"}))

    pending = client.post(f"/chat/threads/{thread}/turns/stream", json={"message": "and paint it"})
    assert pending.status_code == 409
    assert pending.headers["content-type"].startswith("application/json")
    assert pending.json()["detail"]["reason"] == "answer the pending revise confirmation first"

    assert TestClient(client.app).post(f"/chat/threads/{thread}/turns/stream", json={"message": "x"}).status_code == 401
    assert client.post(f"/chat/threads/{uuid4()}/turns/stream", json={"message": "x"}).status_code == 404
    unknown = client.post(
        f"/chat/threads/{thread}/turns/stream", json={"message": "x", "upload_ids": [str(uuid4())]}
    )
    assert unknown.status_code == 422 and unknown.json()["detail"]["failure_class"] == "unknown_upload"
    stale = client.post(f"/chat/threads/{thread}/resume/stream", json={"confirmation_id": "stale", "answer": "yes"})
    assert stale.status_code == 409

    client.app.state.graph = None
    down = client.post(f"/chat/threads/{thread}/turns/stream", json={"message": "x"})
    assert down.status_code == 503 and down.json()["detail"]["failure_class"] == "unavailable"


def test_a_gateway_timeout_ends_the_stream_and_forgets_the_message(client: TestClient) -> None:
    timeout = openai.APITimeoutError(request=httpx2.Request("POST", "https://openrouter.ai/x"))
    install(client, fake_models(foreman={"decisions": [{"specialist": "intake", "reason": "t"}]}, intake={"error": timeout}))
    thread = start(client, title="Hall bench")

    events = events_of(client.post(f"/chat/threads/{thread}/turns/stream", json={"message": "a bench please"}))
    assert [kind for kind, _ in events] == ["specialist", "error", "done"]
    assert events[1][1]["failure_class"] == "timeout"
    assert client.get(f"/chat/threads/{thread}").json()["messages"] == []
    # The streamed turn has ended, so the thread is no longer running and can be deleted.
    assert client.delete(f"/chat/threads/{thread}").status_code == 204


# --- titles (studio-chat-polish) ----------------------------------------------------

FIRST = "I want a listening wall for my records in the living room next to the window"


def _titled_models(title_reply: str = "Listening wall for records"):
    return fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}], "replies": [title_reply]},
        intake={"replies": ["How wide is the wall?"]},
    )


def _title_of(client: TestClient, thread: str) -> str:
    listed = {t["thread_id"]: t["title"] for t in client.get("/chat/threads").json()}
    assert listed[thread] == client.get(f"/chat/threads/{thread}").json()["title"]
    return listed[thread]


def test_an_untitled_thread_is_titled_by_the_foremans_model_after_its_first_turn(client: TestClient) -> None:
    from sqlalchemy import select

    from app.db.models import ModelUsage

    install(client, _titled_models('"Listening wall for records."'))
    thread = start(client)
    assert _title_of(client, thread) == ""
    turn = client.post(f"/chat/threads/{thread}/turns", json={"message": FIRST})
    assert turn.status_code == 200 and turn.json()["reply"] == "How wide is the wall?"
    assert _title_of(client, thread) == "Listening wall for records"

    with Session(client.app.state.engine) as session:
        rows = session.scalars(select(ModelUsage).where(ModelUsage.operation == "chat.title")).all()
    assert [row.model_id for row in rows] == [client.app.state.routing.model_for("foreman")]

    # Only the first turn writes a title.
    client.post(f"/chat/threads/{thread}/turns", json={"message": "about 3 m"})
    assert _title_of(client, thread) == "Listening wall for records"


def test_a_refused_title_call_falls_back_to_the_first_words(client: TestClient) -> None:
    from datetime import UTC, datetime

    from app.db.models import ModelUsage, OperatorSetting

    slug = client.app.state.routing.model_for("foreman")
    with Session(client.app.state.engine) as session:
        session.merge(OperatorSetting(
            key=f"budget:{slug}",
            value=json.dumps({"context_budget_tokens": 32000, "daily_token_ceiling": 50}),
            updated_at=datetime.now(UTC),
        ))
        session.add(ModelUsage(id=uuid4(), model_id=slug, operation="chat.foreman", estimated_tokens=80))
        session.commit()
    install(client, _titled_models())
    thread = start(client)
    turn = client.post(f"/chat/threads/{thread}/turns", json={"message": FIRST})
    assert turn.status_code == 200
    assert "today's limit is reached" in turn.json()["reply"]
    assert _title_of(client, thread) == "I want a listening wall for my records in the living room"


def test_an_owner_title_set_during_the_turn_is_kept(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agent import chat as chat_module

    install(client, _titled_models())
    thread = start(client)
    generated = chat_module.title_for

    def rename_first(graph, **kwargs):
        assert client.patch(f"/chat/threads/{thread}", json={"title": "Listening wall"}).status_code == 200
        return generated(graph, **kwargs)

    monkeypatch.setattr(chat_module, "title_for", rename_first)
    events = events_of(client.post(f"/chat/threads/{thread}/turns/stream", json={"message": FIRST}))
    assert [kind for kind, _ in events] == ["specialist", "reply", "done"]
    assert _title_of(client, thread) == "Listening wall"


def test_a_streamed_first_turn_reports_its_title_before_closing(client: TestClient) -> None:
    install(client, _titled_models())
    thread = start(client)
    events = events_of(client.post(f"/chat/threads/{thread}/turns/stream", json={"message": FIRST}))
    assert [kind for kind, _ in events] == ["specialist", "reply", "title", "done"]
    assert events[2][1] == {"title": "Listening wall for records"}
    assert _title_of(client, thread) == "Listening wall for records"


def test_a_renamed_thread_keeps_its_title_through_later_turns(client: TestClient) -> None:
    install(client, _titled_models())
    thread = start(client)
    renamed = client.patch(f"/chat/threads/{thread}", json={"title": "  Listening wall "})
    assert renamed.status_code == 200 and renamed.json()["title"] == "Listening wall"
    client.post(f"/chat/threads/{thread}/turns", json={"message": FIRST})
    assert _title_of(client, thread) == "Listening wall"


def test_renaming_refuses_an_empty_title_and_an_unknown_thread(client: TestClient) -> None:
    thread = start(client, title="Hall bench")
    assert client.patch(f"/chat/threads/{thread}", json={"title": "   "}).status_code == 422
    assert client.patch(f"/chat/threads/{thread}", json={"title": "x" * 201}).status_code == 422
    assert _title_of(client, thread) == "Hall bench"
    assert client.patch(f"/chat/threads/{uuid4()}", json={"title": "Listening wall"}).status_code == 404
    assert TestClient(client.app).patch(f"/chat/threads/{thread}", json={"title": "x"}).status_code == 401


# --- question sets (studio-chat-polish) ---------------------------------------------

QUESTIONS = {"questions": [{"text": "Ceiling height?", "unit": "mm"}, {"text": "Budget?", "unit": "EUR"}]}


def _asking(client: TestClient, reply: str = "Thanks, noted.") -> tuple[str, dict]:
    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}]},
        intake={"steps": [[tool_call("ask_owner", QUESTIONS)], reply]},
    ))
    thread = start(client, title="Hall bench")
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"})
    assert paused.status_code == 200, paused.text
    return thread, paused.json()["pending"]


def test_questions_are_pending_and_answered_in_one_step(client: TestClient) -> None:
    thread, pending = _asking(client)
    assert pending["kind"] == "questions"
    assert pending["questions"] == [
        {"text": "Ceiling height?", "unit": "mm", "choices": []},
        {"text": "Budget?", "unit": "EUR", "choices": []},
    ]
    assert client.get(f"/chat/threads/{thread}").json()["pending"]["kind"] == "questions"
    blocked = client.post(f"/chat/threads/{thread}/turns", json={"message": "hello?"})
    assert blocked.status_code == 409 and blocked.json()["detail"]["reason"] == "answer the pending questions first"

    answered = client.post(
        f"/chat/threads/{thread}/resume",
        json={"confirmation_id": pending["confirmation_id"], "answers": ["2500", "900"]},
    )
    assert answered.status_code == 200 and answered.json()["reply"] == "Thanks, noted."
    read = client.get(f"/chat/threads/{thread}").json()
    assert read["pending"] is None
    assert {
        "role": "assistant", "text": "", "kind": "answers",
        "rows": [{"question": "Ceiling height?", "answer": "2500 mm"}, {"question": "Budget?", "answer": "900 EUR"}],
    } in read["messages"]


def test_the_wrong_number_or_kind_of_answer_is_refused_and_stays_pending(client: TestClient) -> None:
    thread, pending = _asking(client)
    for body in (
        {"answers": ["2500"]},
        {"answer": "yes"},
        {"answers": ["2500", "900"], "declined": "later"},
        {},
    ):
        refused = client.post(f"/chat/threads/{thread}/resume", json={"confirmation_id": pending["confirmation_id"], **body})
        assert refused.status_code == 422, body
    assert client.get(f"/chat/threads/{thread}").json()["pending"]["confirmation_id"] == pending["confirmation_id"]


def test_declined_questions_continue_with_the_owners_message(client: TestClient) -> None:
    thread, pending = _asking(client, reply="Measure tomorrow, then.")
    declined = client.post(
        f"/chat/threads/{thread}/resume",
        json={"confirmation_id": pending["confirmation_id"], "declined": "I'll measure tomorrow"},
    )
    assert declined.status_code == 200 and declined.json()["pending"] is None
    messages = client.get(f"/chat/threads/{thread}").json()["messages"]
    assert {"role": "owner", "text": "I'll measure tomorrow"} in messages


def test_a_stale_question_id_is_refused(client: TestClient) -> None:
    thread, pending = _asking(client)
    client.post(f"/chat/threads/{thread}/resume", json={"confirmation_id": pending["confirmation_id"], "answers": ["2500", "900"]})
    stale = client.post(
        f"/chat/threads/{thread}/resume",
        json={"confirmation_id": pending["confirmation_id"], "answers": ["2500", "900"]},
    )
    assert stale.status_code == 409


def test_a_confirmation_refuses_answers_meant_for_questions(client: TestClient) -> None:
    install(client, brief_models())
    thread = start(client, title="Hall bench")
    pending = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"}).json()["pending"]
    assert pending["kind"] == "confirmation" and pending["questions"] == []
    wrong = client.post(f"/chat/threads/{thread}/resume", json={"confirmation_id": pending["confirmation_id"], "answers": ["yes"]})
    assert wrong.status_code == 422
    # The old body shape still answers a confirmation.
    right = client.post(f"/chat/threads/{thread}/resume", json={"confirmation_id": pending["confirmation_id"], "answer": "yes"})
    assert right.status_code == 200


def test_a_render_notice_follows_the_reply_that_started_the_render(client: TestClient) -> None:
    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}]},
        intake={"replies": ["Started a draft turntable of hall-bench version 1."]},
    ))
    thread = start(client, title="Hall bench")
    client.post(f"/chat/threads/{thread}/turns", json={"message": "render it"})
    with Session(client.app.state.engine) as session:
        house_file.add_notice(
            session, UUID(thread), after_messages=2, outcome="succeeded", tier="draft",
            text="The draft turntable of hall-bench version 1 is ready. You can also check it in the Piece panel.",
            package_id="hall-bench", version=1,
        )
        house_file.add_notice(
            session, UUID(thread), after_messages=2, outcome="failed", tier="preview",
            text="The preview still of the flat shell version 1 did not finish, so nothing new was published. You can ask for it again.",
        )
        house_file.add_notice(
            session, UUID(thread), after_messages=2, outcome="succeeded", kind="build", tier=None,
            text="hall-bench version 2 is built.", package_id="hall-bench", version=2,
        )
        session.commit()

    messages = client.get(f"/chat/threads/{thread}").json()["messages"]
    assert [m["role"] for m in messages] == ["owner", "assistant", "notice", "notice", "notice"]
    done, failed, built = messages[2], messages[3], messages[4]
    assert [m["kind"] for m in messages[2:]] == ["render", "render", "build"]
    assert "tier" not in built and (built["package_id"], built["version"]) == ("hall-bench", 2)
    assert (done["outcome"], done["tier"], done["package_id"], done["version"]) == ("succeeded", "draft", "hall-bench", 1)
    assert (failed["outcome"], failed["tier"]) == ("failed", "preview")
    assert "package_id" not in failed and "version" not in failed and "package_id" not in messages[0]
    body = json.dumps(messages).lower()
    assert "/home/" not in body and "openai/" not in body and "token" not in body


# --- stop and edit (app-check-2026-10-09) ---------------------------------------------

class Stopping(FakeChatModel):
    """A fake that asks the thread's running turn to stop on its `stop_on`-th call (a
    decision counts for the Foreman), as the owner pressing Stop meanwhile would."""

    thread: str = ""
    stop_on: int = 1
    seen: int = 0

    def _maybe_stop(self) -> None:
        from app.agent import chat

        self.seen += 1
        if self.seen == self.stop_on:
            chat.request_stop(UUID(self.thread))

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any):
        self._maybe_stop()
        return super()._generate(messages, stop, run_manager, **kwargs)

    def with_structured_output(self, schema: Any, **kwargs: Any):
        inner = super().with_structured_output(schema, **kwargs)

        def decide(messages: Any, config: Any = None) -> Any:
            self._maybe_stop()
            return inner.invoke(messages, config)

        return RunnableLambda(decide)


def test_a_turn_stopped_while_the_foreman_chooses_leaves_no_trace(client: TestClient) -> None:
    models = fake_models(intake={"replies": ["Which wall?"]})
    models["foreman"] = Stopping(decisions=[{"specialist": "intake", "reason": "t"}])
    install(client, models)
    thread = start(client, title="Bench")
    models["foreman"].thread = thread

    events = events_of(client.post(f"/chat/threads/{thread}/turns/stream", json={"message": "make it wider"}))
    assert [kind for kind, _ in events] == ["specialist", "stopped", "done"]
    assert events[1][1]["text"].startswith("Stopped. This message and its replies were removed.")
    assert "already started" not in events[1][1]["text"]
    assert models["intake"].calls == 0
    assert client.get(f"/chat/threads/{thread}").json()["messages"] == []
    # The turn has ended: nothing is left to stop.
    assert client.post(f"/chat/threads/{thread}/turns/stop").status_code == 409


def test_a_turn_stopped_after_a_tool_ran_names_it_and_keeps_its_work(client: TestClient, render_root: Path) -> None:
    from app.blender import storage

    _built_bench(client, render_root)
    models = fake_models(foreman={"decisions": [{"specialist": "builder", "reason": "t"}]})
    models["builder"] = Stopping(
        stop_on=2, steps=[[tool_call("blender_build", {"package_id": "hall-bench", "version": 1})], "Built."]
    )
    install(client, models)
    thread = start(client, title="Hall bench", package_id="hall-bench")
    models["builder"].thread = thread

    events = events_of(client.post(f"/chat/threads/{thread}/turns/stream", json={"message": "build it"}))
    kinds = [kind for kind, _ in events]
    assert kinds[-2:] == ["stopped", "done"] and ("tool", {"plugin": "blender build"}) in events
    assert "Already started before the stop and not undone: blender build" in events[-2][1]["text"]
    assert client.get(f"/chat/threads/{thread}").json()["messages"] == []
    assert storage.read_status(storage.version_dir(render_root, "hall-bench", 1))["status"] == "succeeded"


def test_stop_needs_a_running_turn_a_known_thread_and_the_session(client: TestClient) -> None:
    install(client, fake_models())
    thread = start(client)
    nothing = client.post(f"/chat/threads/{thread}/turns/stop")
    assert nothing.status_code == 409 and nothing.json()["detail"]["failure_class"] == "no_turn_running"
    assert client.post(f"/chat/threads/{uuid4()}/turns/stop").status_code == 404
    assert TestClient(client.app).post(f"/chat/threads/{thread}/turns/stop").status_code == 401


def _latest_id(client: TestClient, thread: str) -> str:
    owners = [m for m in client.get(f"/chat/threads/{thread}").json()["messages"] if m.get("message_id")]
    return owners[-1]["message_id"]


def test_the_latest_message_is_edited_and_answered_again(client: TestClient) -> None:
    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}] * 2},
        intake={"replies": ["Which wall?", "45 cm deep, noted."]},
    ))
    thread = start(client, title="Bench")
    client.post(f"/chat/threads/{thread}/turns", json={"message": "make it 60 cm deep"})

    events = events_of(client.post(
        f"/chat/threads/{thread}/turns/latest",
        json={"message_id": _latest_id(client, thread), "message": "make it 45 cm deep"},
    ))
    assert events[0] == ("rewound", {"kept": []})
    assert ("reply", {"reply": "45 cm deep, noted.", "specialists": ["intake"]}) in events
    assert without_ids(client.get(f"/chat/threads/{thread}").json()["messages"]) == [
        {"role": "owner", "text": "make it 45 cm deep"},
        {"role": "assistant", "text": "45 cm deep, noted."},
    ]


def test_an_edit_names_the_version_the_rewound_turn_created(client: TestClient, render_root: Path) -> None:
    from app.blender import storage

    _built_bench(client, render_root)
    models = _designer_revises()
    models["foreman"].decisions.append({"specialist": "designer", "reason": "t"})
    models["designer"].steps.append("Which shelf?")
    install(client, models)
    thread = start(client, title="Hall bench", package_id="hall-bench")
    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "one more shelf"}).json()
    client.post(f"/chat/threads/{thread}/resume", json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"})
    assert storage.versions(render_root, "hall-bench") == [1, 2]

    events = events_of(client.post(
        f"/chat/threads/{thread}/turns/latest",
        json={"message_id": _latest_id(client, thread), "message": "two more shelves"},
    ))
    kind, rewound = events[0]
    assert kind == "rewound" and rewound["kept"][0].startswith("Created hall-bench version 2")
    assert storage.versions(render_root, "hall-bench") == [1, 2]
    shown = without_ids(client.get(f"/chat/threads/{thread}").json()["messages"])
    assert shown[0] == {"role": "owner", "text": "two more shelves"}
    assert {"role": "owner", "text": "one more shelf"} not in shown


def test_only_the_latest_message_can_be_edited(client: TestClient) -> None:
    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}] * 2}, intake={"replies": ["One.", "Two."]},
    ))
    thread = start(client, title="Bench")
    client.post(f"/chat/threads/{thread}/turns", json={"message": "first"})
    client.post(f"/chat/threads/{thread}/turns", json={"message": "second"})
    before = client.get(f"/chat/threads/{thread}").json()["messages"]
    older = before[0]["message_id"]
    refused = client.post(f"/chat/threads/{thread}/turns/latest", json={"message_id": older, "message": "changed"})
    assert refused.status_code == 409 and refused.json()["detail"]["failure_class"] == "not_latest"
    assert client.get(f"/chat/threads/{thread}").json()["messages"] == before


def test_an_edit_while_a_confirmation_is_pending_is_refused_naming_it(client: TestClient, render_root: Path) -> None:
    _built_bench(client, render_root)
    install(client, _designer_revises())
    thread = start(client, title="Hall bench", package_id="hall-bench")
    client.post(f"/chat/threads/{thread}/turns", json={"message": "one more shelf"})
    refused = client.post(
        f"/chat/threads/{thread}/turns/latest", json={"message_id": _latest_id(client, thread), "message": "two"}
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["reason"] == "answer the pending revise confirmation first"


def test_an_edited_message_keeps_the_files_sent_with_it(client: TestClient, tmp_path: Path) -> None:
    from tests.blender_fakes import png_bytes

    client.app.state.settings.upload_root = tmp_path / "uploads"
    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}] * 2}, intake={"replies": ["Seen.", "Seen again."]},
    ))
    thread = start(client, title="Flat")
    upload = client.post(
        f"/chat/threads/{thread}/uploads", files={"file": ("plan.png", png_bytes(8, 8), "image/png")}
    ).json()["upload_id"]
    client.post(f"/chat/threads/{thread}/turns", json={"message": "my flat", "upload_ids": [upload]})
    events_of(client.post(
        f"/chat/threads/{thread}/turns/latest",
        json={"message_id": _latest_id(client, thread), "message": "my flat, ground floor"},
    ))
    first = client.get(f"/chat/threads/{thread}").json()["messages"][0]
    assert first["text"] == "my flat, ground floor" and first["upload_ids"] == [upload]


# --- the Brief panel's routes (split-project-panel) ---------------------------------------------


def test_brief_routes_need_the_session_and_a_known_thread(client: TestClient) -> None:
    install(client, fake_models())
    anonymous = TestClient(client.app)
    assert anonymous.get(f"/chat/threads/{uuid4()}/brief").status_code == 401
    assert anonymous.put(f"/chat/threads/{uuid4()}/brief", json={"purpose": "x"}).status_code == 401
    assert client.get(f"/chat/threads/{uuid4()}/brief").status_code == 404
    assert client.put(f"/chat/threads/{uuid4()}/brief", json={"purpose": "x"}).status_code == 404


def test_brief_is_empty_until_saved_then_holds_the_edit_in_thread_and_piece(client: TestClient) -> None:
    install(client, fake_models())
    thread = start(client, room="Hall")
    with Session(client.app.state.engine) as session:
        house_file.record_piece(session, "hall-bench", "Hall bench", {"purpose": "old", "budget_eur": 400})
        house_file.touch_thread(session, UUID(thread), package_id="hall-bench")
        session.commit()
    first = client.get(f"/chat/threads/{thread}/brief").json()
    assert "Hall" in first["rooms"]
    saved = client.put(
        f"/chat/threads/{thread}/brief",
        json={"room": "Hall", "purpose": "  a bench  ", "budget_eur": 900, "style": "oak", "max_piece_height_mm": 900},
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["confirmed"], body["purpose"], body["budget_eur"], body["style"]) == (True, "a bench", 900, "oak")
    assert client.get(f"/chat/threads/{thread}/brief").json()["budget_eur"] == 900
    with Session(client.app.state.engine) as session:
        piece = session.get(house_file.Piece, "hall-bench")
        assert piece.brief["budget_eur"] == 900
        assert house_file.preferences(session)["budget_eur"] == "900"


def test_a_hand_edited_height_clears_the_raised_by_version_note(client: TestClient) -> None:
    install(client, fake_models())
    thread = start(client, room="Hall")
    url = f"/chat/threads/{thread}/brief"
    from app.agent import chat as chat_module

    chat_module.write_brief(
        client.app.state.graph,
        thread_id=UUID(thread),
        owner_id=uuid4(),
        brief={"purpose": "p", "max_piece_height_mm": 2238, "max_piece_height_from_version": 17},
    )
    same = client.put(url, json={"purpose": "p", "max_piece_height_mm": 2238}).json()
    assert same["max_piece_height_from_version"] == 17
    changed = client.put(url, json={"purpose": "p", "max_piece_height_mm": 2000}).json()
    assert changed["max_piece_height_from_version"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"purpose": "   "},
        {"purpose": "x", "max_piece_height_mm": 0},
        {"purpose": "x", "budget_eur": -1},
        {"purpose": "x", "room": "Nowhere"},
    ],
)
def test_an_invalid_brief_is_refused_and_changes_nothing(client: TestClient, body: dict) -> None:
    install(client, fake_models())
    thread = start(client, room="Hall")
    assert client.put(f"/chat/threads/{thread}/brief", json=body).status_code == 422
    assert client.get(f"/chat/threads/{thread}/brief").json()["confirmed"] is False


def test_a_brief_is_not_saved_while_a_turn_runs(client: TestClient) -> None:
    from app.api import chat as chat_api

    install(client, fake_models())
    thread = start(client, room="Hall")
    chat_api._running.add(UUID(thread))
    try:
        refused = client.put(f"/chat/threads/{thread}/brief", json={"purpose": "x"})
    finally:
        chat_api._running.discard(UUID(thread))
    assert refused.status_code == 409
    assert client.get(f"/chat/threads/{thread}/brief").json()["confirmed"] is False
