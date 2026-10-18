"""dev-panel-insights: call totals, trace links, model prices, the workflow map, guideline uploads and design rules."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.admin_rules import open_items
from app.api.admin_workflow import GUARDED_TOOLS
from app.auth.accounts import ensure_owner
from app.config import Settings
from app.db.models import GuidelineNote, ModelUsage
from app.db.session import make_engine
from app.main import create_app
from conftest import OWNER_EMAIL, OWNER_PASSWORD
from tests.api_helpers import reset_owner, sign_in
from tests.blender_fakes import fake_pipeline_launch
from tests.test_guideline_ingestion import PDF

DESIGNER = "deepseek/deepseek-v4-pro-0813"
REVIEWER = "deepseek/deepseek-v4.1-flash"


def _clean(database_url: str) -> None:
    engine = make_engine(database_url)
    with Session(engine) as session:
        session.execute(text("DELETE FROM model_prices"))
        session.execute(text("DELETE FROM guideline_uploads"))
        session.execute(text("DELETE FROM model_usage"))
        session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'design_rule:%'"))
        session.execute(text("DELETE FROM chunks WHERE url LIKE 'file:pdf/upload-%'"))
        session.commit()
    engine.dispose()


def _make(database_url: str, render_root: Path, binary: Path, guideline_root: Path, *, dev: bool = True) -> TestClient:
    settings = Settings(
        database_url=database_url, openrouter_api_key="sk-or-test", cors_origins="http://localhost:5173",
        owner_email=OWNER_EMAIL, owner_password=OWNER_PASSWORD, gateway_probe_enabled=False,
        dev_panel_enabled=dev, render_root=render_root, blender_bin=binary, guideline_root=guideline_root,
        _env_file=None,
    )
    reset_owner(database_url)
    _clean(database_url)
    app = create_app(settings)
    app.state.blender_launch = fake_pipeline_launch()
    client = TestClient(app)
    client.__enter__()
    return client


@pytest.fixture
def guideline_root(tmp_path: Path) -> Path:
    root = tmp_path / "guidelines"
    (root / "pdf").mkdir(parents=True)
    return root


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path, guideline_root: Path):
    app_client = _make(migrated_database, render_root, fake_blender, guideline_root)
    sign_in(app_client)
    yield app_client
    app_client.__exit__(None, None, None)
    _clean(migrated_database)


def _usage(database_url: str, rows: list[tuple[str, str, int | None, int | None, str | None]]) -> None:
    engine = make_engine(database_url)
    with Session(engine) as session:
        owner = ensure_owner(session, OWNER_EMAIL, OWNER_PASSWORD)
        for model, operation, tokens_in, tokens_out, trace in rows:
            session.add(
                ModelUsage(
                    id=uuid4(), model_id=model, operation=operation, input_tokens=tokens_in, output_tokens=tokens_out,
                    estimated_tokens=50 if tokens_in is None else None, user_id=owner.id, trace_id=trace,
                )
            )
        session.commit()
    engine.dispose()


def _models_list(*priced: tuple[str, str, str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/models"
        data = [{"id": slug, "pricing": {"prompt": prompt, "completion": completion}} for slug, prompt, completion in priced]
        return httpx.Response(200, json={"data": data})

    return httpx.MockTransport(handler)


# --- totals -------------------------------------------------------------------------------------


def test_totals_per_agent_count_each_slots_calls(client: TestClient, migrated_database: str) -> None:
    _usage(migrated_database, [(DESIGNER, "chat.designer", 10, 4, None)] * 3 + [(REVIEWER, "chat.reviewer", 20, 5, None)])
    body = client.get("/admin/usage/summary", params={"days": 7}).json()
    slots = {group["key"]: group for group in body["slot"]}
    assert slots["designer"]["calls"] == 3 and slots["designer"]["input_tokens"] == 30
    assert slots["reviewer"]["calls"] == 1 and slots["reviewer"]["output_tokens"] == 5
    assert {group["key"] for group in body["model"]} == {DESIGNER, REVIEWER}
    assert sum(group["calls"] for group in body["day"]) == 4


def test_an_unpriced_model_counts_calls_but_marks_cost_incomplete(client: TestClient, migrated_database: str) -> None:
    _usage(migrated_database, [(DESIGNER, "chat.designer", 1_000_000, 0, None), (REVIEWER, "chat.reviewer", None, None, None)])
    client.app.state.price_transport = _models_list((DESIGNER, "0.000002", "0.000008"))
    assert client.post("/admin/model-prices/refresh").status_code == 200
    body = client.get("/admin/usage/summary", params={"days": 7}).json()
    models = {group["key"]: group for group in body["model"]}
    assert models[DESIGNER]["cost_usd"] == pytest.approx(2.0) and models[DESIGNER]["cost_complete"]
    assert models[REVIEWER]["calls"] == 1 and models[REVIEWER]["estimated_calls"] == 1
    assert not models[REVIEWER]["cost_complete"] and body["cost_incomplete"]
    assert body["label"] == "estimate at the last fetched price"


def test_a_range_of_45_days_is_refused(client: TestClient) -> None:
    response = client.get("/admin/usage/summary", params={"days": 45})
    assert response.status_code == 422 and "days" in json.dumps(response.json())


# --- trace links --------------------------------------------------------------------------------


class _Tracing:
    enabled = True

    def flush(self) -> None:
        pass

    def trace_url(self, trace_id: str | None) -> str | None:
        return f"https://cloud.langfuse.com/project/p/traces/{trace_id}" if trace_id else None


def _thread(client: TestClient) -> str:
    return client.post("/chat/threads", json={}).json()["thread_id"]


def test_a_call_with_a_trace_links_to_it_and_no_key_is_sent(client: TestClient, migrated_database: str) -> None:
    thread_id = _thread(client)
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        session.add(
            ModelUsage(
                id=uuid4(), model_id=DESIGNER, operation="chat.designer", input_tokens=1, output_tokens=1,
                trace_id="abc", thread_id=thread_id,
            )
        )
        session.commit()
    engine.dispose()
    client.app.state.tracing = _Tracing()
    response = client.get(f"/admin/threads/{thread_id}/calls")
    assert response.json()[0]["trace_url"] == "https://cloud.langfuse.com/project/p/traces/abc"
    assert client.get("/admin/usage/summary").json()["tracing"] is True
    for body in (response.text, client.get("/admin/usage/summary").text, client.get("/admin/models").text):
        assert "pk-lf-" not in body and "sk-lf-" not in body


def test_with_tracing_off_there_is_no_link(client: TestClient, migrated_database: str) -> None:
    thread_id = _thread(client)
    _usage(migrated_database, [])
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        session.add(ModelUsage(id=uuid4(), model_id=DESIGNER, operation="chat.designer", input_tokens=1,
                               output_tokens=1, trace_id="abc", thread_id=thread_id))
        session.commit()
    engine.dispose()
    assert client.get(f"/admin/threads/{thread_id}/calls").json()[0]["trace_url"] is None
    assert client.get("/admin/usage/summary").json()["tracing"] is False


# --- prices -------------------------------------------------------------------------------------


def test_prices_refresh_from_the_model_list_and_an_alias_has_no_price(client: TestClient) -> None:
    client.app.state.price_transport = _models_list((REVIEWER, "0.00000027", "0.0000011"), ("other/model", "1", "1"))
    rows = {row["slug"]: row for row in client.post("/admin/model-prices/refresh").json()}
    assert rows[REVIEWER]["input_per_million_usd"] == pytest.approx(0.27)
    assert rows[REVIEWER]["output_per_million_usd"] == pytest.approx(1.1)
    assert rows[REVIEWER]["fetched_at"] is not None
    assert rows["~deepseek/deepseek-v4-flash-latest"]["input_per_million_usd"] is None
    assert "other/model" not in rows


def test_a_failed_refresh_keeps_the_stored_prices(client: TestClient) -> None:
    client.app.state.price_transport = _models_list((REVIEWER, "0.00000027", "0.0000011"))
    client.post("/admin/model-prices/refresh")

    def down(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    client.app.state.price_transport = httpx.MockTransport(down)
    response = client.post("/admin/model-prices/refresh")
    assert response.status_code == 502 and response.json()["detail"]["failure_class"] == "price_refresh_failed"
    rows = {row["slug"]: row for row in client.get("/admin/model-prices").json()}
    assert rows[REVIEWER]["input_per_million_usd"] == pytest.approx(0.27)


def test_no_homeowner_route_shows_a_price(client: TestClient) -> None:
    client.app.state.price_transport = _models_list((REVIEWER, "0.00000027", "0.0000011"))
    client.post("/admin/model-prices/refresh")
    for path in ("/chat/threads", "/pieces", "/rooms"):
        body = client.get(path).text
        assert "per_million" not in body and "cost_usd" not in body


# --- workflow map -------------------------------------------------------------------------------


def test_the_map_follows_routing_plugins_and_markers(client: TestClient) -> None:
    if client.app.state.graph is None:
        pytest.skip("no checkpointer in this environment")
    client.put("/admin/plugins/render_turntable", json={"enabled": False})
    body = client.get("/admin/workflow").json()
    nodes = {node["name"]: node for node in body["nodes"]}
    assert set(nodes) >= {"foreman", "intake", "designer", "builder", "lighting", "reviewer", "researcher"}
    assert {"from": "foreman", "to": "designer"} in body["handoffs"]
    # The code-only step after Intake is drawn as Intake's hand-off to the Designer (pending-design-import).
    assert "after_intake" not in nodes
    assert {"from": "intake", "to": "designer"} in body["handoffs"]
    assert "after_designer" not in nodes
    assert {"from": "designer", "to": "builder"} in body["handoffs"]
    # The step after the other specialists hands a `compose_room` call on (room-change-goes-to-designer).
    assert "after_specialist" not in nodes
    assert {"from": "builder", "to": "designer"} in body["handoffs"]
    assert nodes["designer"]["model"] == client.app.state.routing.model_for("designer")
    tools = {tool["name"]: tool for node in body["nodes"] for tool in node["tools"]}
    assert tools["render_turntable"]["render_guard"] and not tools["render_turntable"]["enabled"]
    assert tools["render_detail"]["render_guard"]
    assert tools["create_piece"]["confirmation"] and tools["revise_package"]["confirmation"]


def test_every_guarded_tool_is_a_loaded_plugin_tool(client: TestClient) -> None:
    assert GUARDED_TOOLS <= client.app.state.plugins.tool_names()


# --- guideline uploads --------------------------------------------------------------------------


def _upload(client: TestClient, content: bytes, title: str = "ASR A1.2") -> httpx.Response:
    return client.post(
        "/admin/guidelines",
        files={"file": ("asr.pdf", content, "application/pdf")},
        data={"title": title, "jurisdiction": "Germany", "published_on": "2022-01-01", "licence": "BAuA"},
    )


def test_an_uploaded_pdf_is_ingested_and_searchable(client: TestClient, fake_embedder, guideline_root: Path) -> None:
    response = _upload(client, PDF)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["origin"] == "upload" and body["passages"] > 0 and body["error"] is None
    assert (guideline_root / "pdf" / f"{body['id']}.pdf").is_file()
    listed = {row["id"]: row for row in client.get("/admin/guidelines").json()}
    assert listed[body["id"]]["deletable"] is True


@pytest.mark.parametrize(("content", "words"), [(b"\x89PNG\r\n", "not a PDF")])
def test_a_renamed_image_is_refused_and_nothing_is_stored(
    client: TestClient, guideline_root: Path, content: bytes, words: str
) -> None:
    response = _upload(client, content)
    assert response.status_code == 422 and words in response.json()["detail"]["reason"]
    assert response.json()["detail"]["field"] == "file"
    assert list((guideline_root / "pdf").iterdir()) == []


def test_the_same_file_twice_is_refused_naming_the_first(client: TestClient, fake_embedder) -> None:
    first = _upload(client, PDF).json()
    again = _upload(client, PDF, title="Copy")
    assert again.status_code == 422 and first["id"] in again.json()["detail"]["reason"]


def test_a_deleted_upload_loses_its_file_and_passages(client: TestClient, fake_embedder, guideline_root: Path) -> None:
    body = _upload(client, PDF).json()
    assert client.delete(f"/admin/guidelines/{body['id']}").status_code == 204
    assert not (guideline_root / "pdf" / f"{body['id']}.pdf").exists()
    assert body["id"] not in {row["id"] for row in client.get("/admin/guidelines").json()}


def test_a_checked_in_source_cannot_be_deleted(client: TestClient) -> None:
    listed = [row for row in client.get("/admin/guidelines").json() if row["origin"] == "list"]
    if not listed:
        pytest.skip("no checked-in source")
    assert client.delete(f"/admin/guidelines/{listed[0]['id']}").status_code == 409


def test_the_routes_need_the_developer_panel(
    migrated_database: str, render_root: Path, fake_blender: Path, guideline_root: Path
) -> None:
    off = _make(migrated_database, render_root, fake_blender, guideline_root, dev=False)
    try:
        sign_in(off)
        for path in ("/admin/usage/summary", "/admin/model-prices", "/admin/workflow", "/admin/guidelines",
                     "/admin/rules", "/admin/open-items"):
            assert off.get(path).status_code == 404, path
    finally:
        off.__exit__(None, None, None)


# --- design rules and open items ----------------------------------------------------------------


def _note(database_url: str) -> str:
    engine = make_engine(database_url)
    with Session(engine) as session:
        note = GuidelineNote(title="Span table", body="18 mm: 800 mm", citation="book p. 3")
        session.add(note)
        session.commit()
        note_id = str(note.id)
    engine.dispose()
    return note_id


def _span_rule(note_id: str, **overrides) -> dict:
    rule = {
        "id": "shelf-span-18", "applies_to": "piece", "check": "shelf_span_mm_for_thickness",
        "params": {"table": [{"thickness_mm": 18, "max_span_mm": 800}]}, "severity": "warn",
        "source": {"publication": f"owner:{note_id}", "section": "p. 3", "quote": "18 mm: 800 mm"},
    }
    rule.update(overrides)
    return rule


def test_a_rule_added_from_the_panel_applies_without_a_restart(client: TestClient, migrated_database: str) -> None:
    note_id = _note(migrated_database)
    response = client.put("/admin/rules/shelf-span-18", json=_span_rule(note_id))
    assert response.status_code == 200, response.text
    listed = {rule["id"]: rule for rule in response.json()["rules"]}
    assert listed["shelf-span-18"]["origin"] == "panel" and listed["shelf-span-18"]["valid"]
    assert any(rule.id == "shelf-span-18" for rule in client.app.state.design_rules)


def test_a_rule_without_a_source_is_refused_and_nothing_changes(client: TestClient, migrated_database: str) -> None:
    before = client.app.state.design_rules
    rule = _span_rule(_note(migrated_database))
    del rule["source"]
    response = client.put("/admin/rules/shelf-span-18", json=rule)
    assert response.status_code == 422 and response.json()["detail"]["field"] == "source"
    assert client.app.state.design_rules == before


def test_the_shipped_count_rules_are_listed(client: TestClient) -> None:
    listed = {rule["id"]: rule for rule in client.get("/admin/rules").json()["rules"]}
    for rule_id, check in (("shelf-pin-count", "shelf_pin_count_for_width"), ("hinge-count", "hinge_count_for_height")):
        assert listed[rule_id]["origin"] == "file" and listed[rule_id]["check"] == check
        assert listed[rule_id]["severity"] == "warn" and listed[rule_id]["source"]["publication"].startswith("owner:")


def test_a_second_pin_count_rule_is_refused_and_nothing_changes(client: TestClient, migrated_database: str) -> None:
    before = client.app.state.design_rules
    rule = _span_rule(
        _note(migrated_database), id="other-pins", check="shelf_pin_count_for_width",
        params={"table": [{"max_width_mm": 600, "pins": 4}], "beyond": 6},
    )
    response = client.put("/admin/rules/other-pins", json=rule)
    assert response.status_code == 422, response.text
    assert "'shelf-pin-count' and 'other-pins'" in response.json()["detail"]["reason"]
    assert client.app.state.design_rules == before


def test_an_edited_file_rule_resets_to_the_file(client: TestClient) -> None:
    listed = {rule["id"]: rule for rule in client.get("/admin/rules").json()["rules"]}
    original = {key: listed["shelf-bracket-count"][key] for key in ("id", "applies_to", "check", "params", "severity", "source")}
    edited = json.loads(json.dumps(original))
    edited["severity"] = "refuse"
    rules = {rule["id"]: rule for rule in client.put("/admin/rules/shelf-bracket-count", json=edited).json()["rules"]}
    assert rules["shelf-bracket-count"]["origin"] == "edited" and rules["shelf-bracket-count"]["severity"] == "refuse"
    rules = {rule["id"]: rule for rule in client.delete("/admin/rules/shelf-bracket-count").json()["rules"]}
    assert rules["shelf-bracket-count"]["origin"] == "file" and rules["shelf-bracket-count"]["severity"] == "warn"


def test_a_rule_whose_note_was_deleted_is_skipped_at_startup(
    client: TestClient, migrated_database: str, render_root: Path, fake_blender: Path, guideline_root: Path
) -> None:
    note_id = _note(migrated_database)
    client.put("/admin/rules/shelf-span-18", json=_span_rule(note_id))
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        session.execute(text("DELETE FROM guideline_notes WHERE id = :id"), {"id": note_id})
        session.commit()
    engine.dispose()
    settings_root = guideline_root
    restarted = TestClient(client.app)
    restarted.__enter__()
    try:
        sign_in(restarted)
        rules = {rule["id"]: rule for rule in restarted.get("/admin/rules").json()["rules"]}
        assert not rules["shelf-span-18"]["valid"] and note_id in rules["shelf-span-18"]["problem"]
        assert all(rule.id != "shelf-span-18" for rule in restarted.app.state.design_rules)
    finally:
        restarted.__exit__(None, None, None)
    assert settings_root.exists()


def test_the_checked_in_table_is_never_rewritten(client: TestClient, migrated_database: str) -> None:
    path = Path(__file__).resolve().parents[1] / "config" / "design_rules.yaml"
    before = path.read_bytes()
    client.put("/admin/rules/shelf-span-18", json=_span_rule(_note(migrated_database)))
    assert path.read_bytes() == before


def test_open_owner_items_are_listed_and_tests_are_left_out(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "design_rules.yaml").write_text("x: 1\n# TODO(user): even_tolerance_mm is yours\n")
    (tmp_path / "app" / "tests").mkdir(parents=True)
    (tmp_path / "app" / "tests" / "test_x.py").write_text("# TODO(user): not this one\n")
    assert open_items(tmp_path) == [
        {"file": "config/design_rules.yaml", "line": 2, "text": "even_tolerance_mm is yours"}
    ]


def test_the_cli_ingestion_includes_uploaded_sources(
    client: TestClient, fake_embedder, guideline_root: Path, migrated_database: str
) -> None:
    from app.guidelines.ingest import ingest_guidelines

    body = _upload(client, PDF).json()
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        report = ingest_guidelines(session, None, root=guideline_root)
    engine.dispose()
    assert report.ingested.get(body["id"], 0) > 0
