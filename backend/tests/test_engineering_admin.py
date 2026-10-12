from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models import EngineeringChunk, KnowledgeSourceVersion
from app.engineering.__main__ import seed_catalogue
from tests.api_helpers import sign_in
from tests.test_dev_panel_insights_api import _make
from tests.test_guideline_ingestion import PDF


@pytest.fixture
def client(migrated_database, render_root, fake_blender, tmp_path):
    client = _make(migrated_database, render_root, fake_blender, tmp_path)
    sign_in(client)
    yield client
    with Session(client.app.state.engine) as session:
        session.execute(text("TRUNCATE knowledge_sources CASCADE"))
        session.commit()
    client.__exit__(None, None, None)


def register(client):
    response = client.post(
        "/admin/knowledge",
        json={
            "key": f"test-{uuid4().hex}",
            "metadata": {"title": "Original fixture"},
            "collections": ["material_datasheets"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_registration_and_seeding_are_metadata_only(client, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Registration must never fetch/extract/embed")

    monkeypatch.setattr("app.engineering.ingest.embed", forbidden)
    identifier = register(client)
    row = next(
        row for row in client.get("/admin/knowledge").json() if row["id"] == identifier
    )
    assert (
        row["passages"] == 0
        and row["rights_status"] == "pending_or_revoked"
        and row["verification_status"] == "unverified"
    )
    with Session(client.app.state.engine) as session:
        before = session.scalar(
            select(func.count()).select_from(KnowledgeSourceVersion)
        )
        assert seed_catalogue(session) == 0
        assert before == session.scalar(
            select(func.count()).select_from(KnowledgeSourceVersion)
        )
        assert session.scalar(select(func.count()).select_from(EngineeringChunk)) == 0


def test_rights_and_review_are_separate_and_staging_does_not_ingest(client):
    identifier = register(client)
    assert (
        client.post(
            f"/admin/knowledge/{identifier}/rights",
            json={"action": "approve", "grants": {}, "evidence": "", "reviewer": ""},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/admin/knowledge/{identifier}/file", files={"file": ("test.pdf", PDF)}
        ).status_code
        == 422
    )
    approved = client.post(
        f"/admin/knowledge/{identifier}/rights",
        json={
            "action": "approve",
            "grants": {"retention": {}},
            "evidence": "Original fixture author permits storage only",
            "reviewer": "fixture author",
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["verification_status"] == "unverified"
    staged = client.post(
        f"/admin/knowledge/{identifier}/file", files={"file": ("test.pdf", PDF)}
    )
    assert staged.status_code == 200 and staged.json()["passages"] == 0
    run = client.post(f"/admin/knowledge/{identifier}/ingest", json=None).json()
    assert run["state"] == "failed" and run["blocks"] == 0
    reviewed = client.post(
        f"/admin/knowledge/{identifier}/review",
        json={"status": "verified", "reviewer": "technical fixture reviewer"},
    ).json()
    assert reviewed["verification_status"] == "verified" and list(
        reviewed["grants"]
    ) == ["retention"]
    revoked = client.post(
        f"/admin/knowledge/{identifier}/rights",
        json={
            "action": "revoke",
            "evidence": "withdrawn",
            "reviewer": "fixture author",
        },
    ).json()
    assert (
        revoked["rights_status"] == "pending_or_revoked" and len(revoked["rights"]) == 2
    )


def test_property_edit_requires_provenance_and_review_stays_explicit(
    client, fake_embedder
):
    identifier = register(client)
    rights = {
        name: {}
        for name in (
            "extraction",
            "local_embedding",
            "local_retrieval",
            "remote_model_use",
            "retention",
        )
    }
    response = client.post(
        f"/admin/knowledge/{identifier}/rights",
        json={
            "action": "approve",
            "grants": rights,
            "evidence": "Original test author",
            "reviewer": "test author",
        },
    )
    assert response.status_code == 200, response.text
    blocks = [
        {
            "block_id": "row-1",
            "kind": "table",
            "content": "Test elastic modulus 2 GPa",
            "pages": [1],
            "headers": ["E (GPa)"],
            "verification_status": "verified",
            "reviewed_by": "fixture author",
        }
    ]
    assert (
        client.post(f"/admin/knowledge/{identifier}/ingest", json=blocks).json()[
            "state"
        ]
        == "published"
    )
    data = {
        "block_id": "missing",
        "kind": "E_MPa",
        "original_unit": "GPa",
        "original_value": 2,
        "value_basis": "mean",
        "page_section": "p. 1",
        "conditions": {"moisture": "dry"},
    }
    assert (
        client.post(f"/admin/knowledge/{identifier}/properties", json=data).status_code
        == 422
    )
    data["block_id"] = "row-1"
    candidate = client.post(
        f"/admin/knowledge/{identifier}/properties", json=data
    ).json()["properties"][0]
    assert (
        candidate["value"] == 2000 and candidate["verification_status"] == "unverified"
    )
    data["original_value"] = 2.1
    edited = client.put(
        f"/admin/knowledge/properties/{candidate['id']}", json=data
    ).json()["properties"][0]
    assert edited["value"] == 2100 and edited["verification_status"] == "unverified"
    reviewed = client.post(
        f"/admin/knowledge/properties/{candidate['id']}/review",
        json={"status": "verified", "reviewer": "fixture technical reviewer"},
    ).json()
    assert reviewed["properties"][0]["verification_status"] == "verified"
    assert (
        client.put(
            f"/admin/knowledge/properties/{candidate['id']}", json=data
        ).status_code
        == 422
    )


@pytest.mark.parametrize("dev", [True, False])
def test_developer_gate(migrated_database, render_root, fake_blender, tmp_path, dev):
    client = _make(migrated_database, render_root, fake_blender, tmp_path, dev=dev)
    try:
        assert client.get("/admin/knowledge").status_code == (401 if dev else 404)
        sign_in(client)
        assert client.get("/admin/knowledge").status_code == (200 if dev else 404)
    finally:
        client.__exit__(None, None, None)


def test_api_tracing_suppresses_content_and_later_calls_keep_local_usage(
    client, fake_embedder, tmp_path, detach_tracing
):
    import json
    from uuid import UUID

    from app.db.models import ModelUsage
    from app.observability.langfuse import Tracing
    from app.plugins.enablement import set_global_enabled, set_thread_enabled
    from tests.fakes import tool_call
    from tests.graph_helpers import fake_models
    from tests.test_chat_api import install, start
    from tests.test_engineering_retrieval import publish
    from tests.test_langfuse_tracing import FakeClient, FakeHandler, _configured

    class Exporter(FakeClient):
        def __init__(self):
            super().__init__()
            self.observations, self.events = [], []

        def start_as_current_observation(self, **fields):
            self.observations.append(fields)
            return super().start_as_current_observation(**fields)

        def create_event(self, **fields):
            self.events.append(fields)

    exporter, handler = Exporter(), FakeHandler()
    client.app.state.tracing = detach_tracing(
        Tracing(_configured(), handler_factory=lambda _: (exporter, handler))
    )
    with Session(client.app.state.engine) as session:
        version = publish(session, tmp_path)
        session.commit()

        evidence_id = f"{version.id}:row-1"
    models = fake_models(
        foreman={
            "decisions": [
                {"specialist": "researcher", "reason": "engineering"},
                {"specialist": "researcher", "reason": "followup"},
            ]
        },
        researcher={
            "steps": [
                [
                    tool_call(
                        "search_engineering_knowledge",
                        {"query": "TEST board", "mode": "keyword"},
                    )
                ],
                json.dumps({"evidence_ids": [evidence_id]}),
                "ordinary follow-up",
            ]
        },
    )
    install(client, models)
    thread = start(client, room=None)
    with Session(client.app.state.engine) as session:
        set_global_enabled(session, "engineering_knowledge", True)
        set_thread_enabled(
            session,
            client.app.state.plugins,
            UUID(thread),
            "engineering_knowledge",
            True,
        )
        session.commit()
    first = client.post(
        f"/chat/threads/{thread}/turns", json={"message": "TEST board load capacity?"}
    )
    assert first.status_code == 200 and "NOT VERIFIED" in first.json()["reply"]
    assert (
        client.post(
            f"/chat/threads/{thread}/turns", json={"message": "Thanks; what next?"}
        ).status_code
        == 200
    )
    assert handler.chains == 0
    assert len(exporter.observations) == 2 and all(
        row["input"] is None for row in exporter.observations
    )
    exported = repr((exporter.observations, exporter.updates, exporter.events))
    assert (
        "2000" not in exported
        and "Dry service" not in exported
        and "TEST board" not in exported
    )
    assert exporter.events and "duration_ms" in exported
    with Session(client.app.state.engine) as session:
        usage = session.scalars(
            select(ModelUsage).where(ModelUsage.thread_id == UUID(thread))
        ).all()
        assert usage and all(row.input_tokens is not None for row in usage)
        set_global_enabled(session, "engineering_knowledge", False)
        session.commit()


def test_developer_method_controls_cannot_enable_unimplemented_unreviewed_equations(
    client,
):
    methods = client.get("/admin/engineering-methods")
    assert methods.status_code == 200
    assert len(methods.json()) == 8 and not any(
        row["enabled"] for row in methods.json()
    )
    shelf = next(row for row in methods.json() if row["id"] == "shelf_immediate")
    data = {
        "method_version": shelf["version"],
        "definition_hash": shelf["definition_hash"],
        "action": "accept",
        "reviewer": "fixture developer",
        "qualification_evidence": "No actual qualification asserted in this negative test",
        "evidence": "Attempt without implemented equations or independent references",
    }
    refused = client.post(
        "/admin/engineering-methods/shelf_immediate/review", json=data
    )
    assert refused.status_code == 422 and "references" in refused.text
    data["action"] = "disable"
    for field in ("reviewer", "qualification_evidence", "evidence"):
        assert (
            client.post(
                "/admin/engineering-methods/shelf_immediate/review",
                json={**data, field: " "},
            ).status_code
            == 422
        )
    assert (
        client.post(
            "/admin/engineering-methods/shelf_immediate/review", json=data
        ).json()["enabled"]
        is False
    )
    assert (
        client.post(
            "/admin/engineering-methods/eval/arbitrary/review", json=data
        ).status_code
        == 404
    )
    assert (
        client.put(
            "/admin/plugins/engineering_knowledge", json={"enabled": True}
        ).status_code
        == 422
    )


def test_owner_report_routes_are_piece_version_scoped_and_cannot_set_visual_approval(
    client,
):
    import json
    from uuid import UUID

    from app.agent import house_file
    from app.db.models import PieceVersion
    from app.engineering.assessments import AssessmentIn
    from app.engineering.reports import generate_report, save_assessment
    from tests.api_helpers import desk

    package = "report-api-" + uuid4().hex[:10]
    root = client.app.state.settings.render_root
    folder = root / package / "v1"
    folder.mkdir(parents=True)
    (folder / "input.json").write_text(json.dumps(desk()))
    with Session(client.app.state.engine) as session:
        house_file.record_piece(session, package, "Original TEST piece")
        house_file.record_version(session, package, 1)
        assessment = save_assessment(
            session,
            root,
            package,
            AssessmentIn(version=1, furniture="shelf"),
            owner_id=UUID(client.get("/auth/me").json()["id"]),
            thread_id=None,
            confirmed=True,
        )
        report = generate_report(session, root, assessment)
        session.commit()
        report_id = str(report.id)
    path = f"/packages/{package}/versions/1/engineering/reports"
    assert client.get(path).status_code == 200
    response = client.get(f"{path}/{report_id}")
    assert response.status_code == 200 and response.json()["overall"] == "INCOMPLETE"
    assert (
        client.get(
            f"/packages/another-piece/versions/1/engineering/reports/{report_id}"
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/packages/{package}/versions/2/engineering/reports/{report_id}"
        ).status_code
        == 404
    )
    with Session(client.app.state.engine) as session:
        assert session.get(PieceVersion, (package, 1)).approved_at is None


def test_catalogue_entry_registers_only_on_request_as_unverified_metadata(client):
    with Session(client.app.state.engine) as session:
        session.execute(text("TRUNCATE knowledge_sources CASCADE"))
        session.commit()
    listed = client.get("/admin/knowledge/catalogue").json()
    entry = next(item for item in listed if item["key"] == "usda-wood-handbook-2021")
    assert entry["metadata"]["source_url"].endswith("62200.pdf")
    registered = client.post(
        "/admin/knowledge/catalogue/usda-wood-handbook-2021/register"
    )
    assert registered.status_code == 201, registered.text
    body = registered.json()
    assert (
        body["verification_status"] == "unverified"
        and body["rights_status"] == "pending_or_revoked"
        and body["passages"] == 0
        and body["reviewed_by"] is None
        and body["rights"] == []
    )
    after = client.get("/admin/knowledge/catalogue").json()
    assert all(item["key"] != "usda-wood-handbook-2021" for item in after)
    missing = client.post("/admin/knowledge/catalogue/usda-wood-handbook-2021/register")
    assert missing.status_code == 404


def _link_version(client, url="https://manual.test/file.pdf"):
    response = client.post(
        "/admin/knowledge",
        json={
            "key": f"test-{uuid4().hex}",
            "metadata": {"title": "Linked fixture", "source_url": url},
            "collections": ["material_datasheets"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_ingest_link_needs_a_link_rights_and_no_staged_file(client, monkeypatch):
    class Silent:
        def __init__(self, settings, *, max_bytes):
            pass

        def __enter__(self):
            raise AssertionError("no fetch may happen")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("app.api.admin_knowledge.KnowledgeFetcher", Silent)
    no_link = register(client)
    refused = client.post(f"/admin/knowledge/{no_link}/ingest-link")
    assert (
        refused.status_code == 422 and refused.json()["detail"]["field"] == "source_url"
    )
    linked = _link_version(client)
    run = client.post(f"/admin/knowledge/{linked}/ingest-link").json()
    assert run["state"] == "failed" and "documented rights" in run["reason"]
    client.post(
        f"/admin/knowledge/{linked}/rights",
        json={
            "action": "approve",
            "grants": {"retention": {}},
            "evidence": "fixture",
            "reviewer": "fixture author",
        },
    )
    client.post(f"/admin/knowledge/{linked}/file", files={"file": ("a.pdf", PDF)})
    refused = client.post(f"/admin/knowledge/{linked}/ingest-link")
    assert (
        refused.status_code == 422 and refused.json()["detail"]["field"] == "local_path"
    )


def test_ingest_link_uses_the_larger_cap_and_honours_robots(client, monkeypatch):
    seen = {}

    class Fetcher:
        def __init__(self, settings, *, max_bytes):
            seen["max_bytes"] = max_bytes

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def fetch_rules(self, base, *, source):
            return type("Rules", (), {"allows": lambda self, url: False})()

    monkeypatch.setattr("app.api.admin_knowledge.KnowledgeFetcher", Fetcher)
    linked = _link_version(client)
    grants = {
        name: {}
        for name in ("extraction", "local_embedding", "local_retrieval", "retention")
    }
    client.post(
        f"/admin/knowledge/{linked}/rights",
        json={
            "action": "approve",
            "grants": grants,
            "evidence": "fixture",
            "reviewer": "fixture author",
        },
    )
    response = client.post(f"/admin/knowledge/{linked}/ingest-link")
    settings = client.app.state.settings
    assert seen["max_bytes"] == settings.engineering_link_max_bytes
    assert settings.engineering_link_max_bytes > settings.guideline_upload_max_bytes
    run = response.json()
    assert run["state"] == "failed" and "robots" in run["reason"] and run["blocks"] == 0


def test_link_cap_applies_only_to_the_explicit_fetcher(settings):
    import httpx

    from app.engineering.fetch import KnowledgeFetcher

    settings.ingestion_min_interval_seconds = 0
    body = b"x" * 2048

    def public(host, port, **kwargs):
        return [(2, 1, 6, "", ("8.8.8.8", port))]

    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    default = KnowledgeFetcher(settings, resolver=public, transport=transport)
    capped = KnowledgeFetcher(
        settings, resolver=public, transport=transport, max_bytes=1024
    )
    with default:
        assert len(default.fetch_page("https://manual.test/a.pdf").content) == 2048
    with capped, pytest.raises(ValueError, match="exceeds"):
        capped.fetch_page("https://manual.test/a.pdf")
