"""feedback-capture: rating renders, the homeowner's view, the developer's summary."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import RenderFeedback, RenderRun
from app.observability.langfuse import Tracing
from app.render import benchmark_store as store
from tests.api_helpers import create, make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch, png_bytes
from tests.test_admin_models_api import _client as dev_client
from tests.test_langfuse_tracing import FakeClient, FakeHandler, _configured

BASE = "/packages/hall-bench/versions/1"
BUILDER_MODEL = "deepseek/deepseek-v4-pro-0813"
PROMPT = "make it look like proper oak please"


def clean_runs(client: TestClient) -> None:
    with Session(client.app.state.engine) as session:
        session.execute(delete(RenderRun))
        session.commit()


def prepared(client: TestClient) -> TestClient:
    sign_in(client)
    store.write_benchmark(client.app.state.engine, 2.5, blender_version="5.2.1 LTS")
    clean_runs(client)
    assert create(client).status_code == 202
    return client


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = dev_client(migrated_database, render_root, fake_blender, dev=True)
    yield prepared(c)
    c.__exit__(None, None, None)


def render(client: TestClient, kind: str = "still", tier: str = "draft") -> None:
    assert client.post(f"{BASE}/renders", json={"kind": kind, "tier": tier}).status_code == 202


def rate(client: TestClient, key: str = "still", rating: str = "down", comment: str | None = "too dark"):
    body = {"rating": rating, **({"comment": comment} if comment is not None else {})}
    return client.put(f"{BASE}/renders/{key}/feedback", json=body)


def feedback_rows(client: TestClient) -> list[RenderFeedback]:
    with Session(client.app.state.engine) as session:
        return list(session.scalars(select(RenderFeedback)))


def item(client: TestClient, key: str) -> dict:
    return next(i for i in client.get(f"{BASE}/renders").json() if i["render"] == key)


# --- rating -----------------------------------------------------------------------------------


def test_a_thumbs_down_with_a_comment_is_stored_and_shown(client: TestClient) -> None:
    render(client)
    response = rate(client)
    assert response.status_code == 200
    body = response.json()
    assert (body["render"], body["tier"], body["rating"], body["comment"]) == ("still", "draft", "down", "too dark")
    assert item(client, "still")["rating"] == "down"
    assert item(client, "still")["preview"] == f"{BASE}/files/still.png"


def test_rating_again_replaces_the_rating(client: TestClient) -> None:
    render(client)
    rate(client)
    assert rate(client, rating="up", comment=None).json()["rating"] == "up"
    [row] = feedback_rows(client)
    assert (row.rating, row.comment) == ("up", None)


def test_clearing_removes_the_rating_and_is_repeatable(client: TestClient) -> None:
    render(client)
    rate(client)
    for _ in range(2):
        response = client.delete(f"{BASE}/renders/still/feedback")
        assert response.status_code == 200 and response.json()["rating"] is None
    assert feedback_rows(client) == []


def test_a_re_rendered_render_starts_unrated_and_the_old_rating_stays_with_the_old_run(
    client: TestClient,
) -> None:
    render(client, tier="draft")
    rate(client)
    render(client, tier="draft")
    assert item(client, "still")["rating"] is None and item(client, "still")["tier"] == "draft"
    assert len(feedback_rows(client)) == 1
    assert rate(client, rating="up", comment=None).status_code == 200
    assert len(feedback_rows(client)) == 2


def test_a_render_that_does_not_exist_cannot_be_rated(client: TestClient) -> None:
    response = rate(client, "still")
    assert response.status_code == 409
    assert response.json()["detail"]["failure_class"] == "no_render"
    assert "does not exist yet" in response.json()["detail"]["reason"]
    assert client.delete(f"{BASE}/renders/still/feedback").status_code == 409


def test_a_render_made_before_ratings_existed_is_listed_but_cannot_be_rated(client: TestClient) -> None:
    folder = client.app.state.settings.render_root / "hall-bench" / "v1"
    (folder / "still.png").write_bytes(png_bytes(600, 600))
    listed = item(client, "still")
    assert listed["can_rate"] is False and listed["rating"] is None
    assert rate(client, "still").status_code == 409


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"rating": "sideways"}, "rating"),
        ({}, "rating"),
        ({"rating": "up", "comment": "x" * 1001}, "1000"),
        ({"rating": "up", "comment": 5}, "comment"),
        ({"rating": "up", "model": "x"}, "model"),
    ],
)
def test_an_invalid_rating_is_refused_naming_the_problem(client: TestClient, body: dict, field: str) -> None:
    render(client)
    response = client.put(f"{BASE}/renders/still/feedback", json=body)
    assert response.status_code == 422 and field in json.dumps(response.json())
    assert feedback_rows(client) == []


def test_an_unknown_render_is_not_found(client: TestClient) -> None:
    assert rate(client, "ultra").status_code == 404


def test_a_comment_of_exactly_a_thousand_characters_is_kept(client: TestClient) -> None:
    render(client)
    assert rate(client, comment="x" * 1000).json()["comment"] == "x" * 1000


def test_every_route_needs_the_owner_cookie(migrated_database: str, render_root: Path, fake_blender: Path) -> None:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    try:
        assert c.get(f"{BASE}/renders").status_code == 401
        assert c.put(f"{BASE}/renders/still/feedback", json={"rating": "up"}).status_code == 401
        assert c.delete(f"{BASE}/renders/still/feedback").status_code == 401
    finally:
        c.__exit__(None, None, None)


# --- the homeowner sees no internals ------------------------------------------------------------


def test_no_slot_model_or_prompt_in_any_homeowner_response(client: TestClient) -> None:
    render(client, kind="turntable")
    with Session(client.app.state.engine) as session:
        run = session.scalars(select(RenderRun).where(RenderRun.render_key == "turntable")).one()
        run.slot, run.model, run.prompt, run.trace_id = "builder", BUILDER_MODEL, PROMPT, "trace-9"
        session.commit()
    responses = [
        client.get(f"{BASE}/renders"),
        rate(client, "turntable"),
        client.get(BASE),
        client.get(f"{BASE}/files/status.json"),
        client.delete(f"{BASE}/renders/turntable/feedback"),
    ]
    for response in responses:
        assert response.status_code == 200
        text = response.text
        for secret in (BUILDER_MODEL, PROMPT, "trace-9", "deepseek", '"slot"', '"model"', '"prompt"'):
            assert secret not in text


# --- tracing never matters ----------------------------------------------------------------------


def test_a_rating_is_traced_and_survives_tracing_failing(client: TestClient, detach_tracing) -> None:
    render(client)
    langfuse = FakeClient()
    scores: list[dict] = []
    langfuse.create_score = lambda **kwargs: scores.append(kwargs)  # type: ignore[attr-defined]
    client.app.state.tracing = detach_tracing(
        Tracing(_configured(), handler_factory=lambda _s: (langfuse, FakeHandler()))
    )
    with Session(client.app.state.engine) as session:
        session.scalars(select(RenderRun)).first().trace_id = "t" * 32
        session.commit()
    assert rate(client).status_code == 200
    assert scores and scores[0]["trace_id"] == "t" * 32

    def explode(**_kwargs):
        raise ConnectionError("langfuse unreachable")

    langfuse.create_score = explode  # type: ignore[attr-defined]
    assert rate(client, rating="up", comment=None).status_code == 200
    assert feedback_rows(client)[0].rating == "up"


# --- the developer's summary ---------------------------------------------------------------------


def add_rated(client: TestClient, *, slot, model, tier, rating, comment=None, age_days: float = 0) -> None:
    when = datetime.now(UTC) - timedelta(days=age_days)
    with Session(client.app.state.engine) as session:
        run = RenderRun(
            id=uuid4(), package_id="hall-bench", version=1, render_key="turntable", tier=tier,
            outcome="succeeded", slot=slot, model=model, started_at=when,
        )
        session.add(run)
        session.flush()
        session.add(
            RenderFeedback(run_id=run.id, rating=rating, comment=comment, created_at=when, updated_at=when)
        )
        session.commit()


def test_the_summary_counts_ratings_per_slot_model_and_tier(client: TestClient) -> None:
    clean_runs(client)
    add_rated(client, slot="builder", model=BUILDER_MODEL, tier="draft", rating="up")
    add_rated(client, slot="builder", model=BUILDER_MODEL, tier="draft", rating="up")
    add_rated(client, slot="builder", model=BUILDER_MODEL, tier="draft", rating="down", comment="too dark")
    add_rated(client, slot="builder", model=BUILDER_MODEL, tier="final", rating="up")
    add_rated(client, slot=None, model=None, tier="draft", rating="up")
    rows = client.get("/admin/feedback").json()
    by = {(r["slot"], r["model"], r["tier"]): r for r in rows}
    draft = by[("builder", BUILDER_MODEL, "draft")]
    assert (draft["up"], draft["down"]) == (2, 1) and draft["latest_comment_at"] is not None
    assert by[("builder", BUILDER_MODEL, "final")]["up"] == 1
    ungrouped = by[(None, None, "draft")]
    assert (ungrouped["up"], ungrouped["down"], ungrouped["latest_comment_at"]) == (1, 0, None)


def test_the_summary_window_excludes_older_ratings(client: TestClient) -> None:
    clean_runs(client)
    add_rated(client, slot="builder", model=BUILDER_MODEL, tier="draft", rating="up", age_days=40)
    assert client.get("/admin/feedback", params={"days": 30}).json() == []
    assert client.get("/admin/feedback", params={"days": 90}).json()[0]["up"] == 1


def test_comments_of_a_group_come_newest_first_and_empty_params_select_the_ungrouped(client: TestClient) -> None:
    clean_runs(client)
    add_rated(client, slot="builder", model=BUILDER_MODEL, tier="draft", rating="down", comment="old", age_days=3)
    add_rated(client, slot="builder", model=BUILDER_MODEL, tier="draft", rating="down", comment="new", age_days=1)
    add_rated(client, slot="builder", model=BUILDER_MODEL, tier="draft", rating="up")  # no comment
    add_rated(client, slot=None, model=None, tier="draft", rating="up", comment="by hand")
    grouped = client.get(
        "/admin/feedback/comments", params={"slot": "builder", "model": BUILDER_MODEL, "tier": "draft"}
    ).json()
    assert [c["comment"] for c in grouped] == ["new", "old"]
    ungrouped = client.get("/admin/feedback/comments", params={"tier": "draft"}).json()
    assert [c["comment"] for c in ungrouped] == ["by hand"]


def test_the_developer_routes_answer_404_when_the_panel_is_disabled(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    c = dev_client(migrated_database, render_root, fake_blender, dev=False)
    sign_in(c)
    try:
        assert c.get("/admin/feedback").status_code == 404
        assert c.get("/admin/feedback/comments", params={"tier": "draft"}).status_code == 404
    finally:
        c.__exit__(None, None, None)


def test_the_summary_needs_the_owner_session(migrated_database: str, render_root: Path, fake_blender: Path) -> None:
    c = dev_client(migrated_database, render_root, fake_blender, dev=True)
    try:
        assert c.get("/admin/feedback").status_code == 401
    finally:
        c.__exit__(None, None, None)


def test_the_run_count_helper_is_sane(client: TestClient) -> None:
    render(client)
    with Session(client.app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(RenderRun)) == 1


# --- restyle variants are rateable renders (two-tier-renders) ---------------------------------


def published_variant(client: TestClient, render_root: Path, variant: str = "walnut-draft") -> None:
    """A published draft turntable variant of hall-bench v1 and its succeeded run."""
    from app.blender import storage
    from app.restyle import store as restyle_store

    folder = restyle_store.variant_dir(storage.version_dir(render_root, "hall-bench", 1), variant)
    (folder / "frames").mkdir(parents=True)
    for index in range(12):
        (folder / "frames" / f"frame_{index:03d}.png").write_bytes(png_bytes(800, 800))
    (folder / "still.png").write_bytes(png_bytes(800, 800))
    (folder / "viewer.html").write_text("<html></html>", encoding="utf-8")
    (folder / "scene.json").write_text(
        json.dumps({"source": "restyle", "label": "Walnut", "tier": "draft", "created_at": "2026-10-15T10:00:00+00:00"}),
        encoding="utf-8",
    )
    with Session(client.app.state.engine) as session:
        session.add(RenderRun(
            package_id="hall-bench", version=1, render_key=f"variant:{variant}", tier="draft",
            outcome="succeeded", slot="builder", model=BUILDER_MODEL,
        ))
        session.commit()


def test_a_variant_is_listed_with_its_frames_and_rated(client: TestClient, render_root: Path) -> None:
    published_variant(client, render_root)
    listed = item(client, "variant:walnut-draft")
    assert (listed["label"], listed["tier"], listed["frames"]) == ("Walnut", "draft", 12)
    assert listed["preview"] == f"{BASE}/files/variants/walnut-draft/frames/0"
    assert listed["can_rate"] is True and listed["finished_at"] == "2026-10-15T10:00:00+00:00"
    response = rate(client, key="variant:walnut-draft", rating="up", comment="love this")
    assert response.status_code == 200
    assert (response.json()["rating"], response.json()["comment"]) == ("up", "love this")
    [row] = feedback_rows(client)
    assert (row.rating, row.comment) == ("up", "love this")
    assert client.delete(f"{BASE}/renders/variant:walnut-draft/feedback").json()["rating"] is None


def test_an_unknown_variant_is_refused_as_not_rendered_yet(client: TestClient, render_root: Path) -> None:
    published_variant(client, render_root)
    response = rate(client, key="variant:sage-green-draft", rating="up")
    assert response.status_code == 409
    assert "does not exist yet" in response.json()["detail"]["reason"]
    assert feedback_rows(client) == []


def test_a_variant_frame_is_served_by_index_and_an_unknown_variant_is_not_found(
    client: TestClient, render_root: Path
) -> None:
    published_variant(client, render_root)
    frame = client.get(f"{BASE}/files/variants/walnut-draft/frames/5")
    assert frame.status_code == 200 and frame.headers["content-type"] == "image/png"
    assert client.get(f"{BASE}/files/variants/walnut-draft/frames/frame_005.png").status_code == 200
    assert client.get(f"{BASE}/files/variants/oak-draft/frames/0").status_code == 404
    assert client.get(f"{BASE}/files/variants/walnut-draft/frames/12").status_code == 404


def test_the_render_list_carries_frame_counts_and_finish_times(client: TestClient) -> None:
    render(client, kind="turntable")
    listed = item(client, "turntable")
    assert listed["frames"] == 12 and listed["finished_at"]
    render(client, kind="still")
    assert item(client, "still")["frames"] == 0
