"""Engineering boundaries exercised on the graph and the actual gateway wire."""

import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.agent.budget import BudgetRefused, RequestBudget, prepare
from app.agent.models.openrouter_client import build_chat_model
from app.agent.summaries import transcript
from app.db.models import EngineeringEvidenceUse
from app.engineering.chat import missing_inputs, render_answer, request_history
from app.engineering.registry import add_property, decide_rights
from app.engineering.schemas import PropertyIn, RightsIn
from app.observability.langfuse import Tracing, mask_personal_data
from app.plugins.enablement import set_global_enabled, set_thread_enabled
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness
from tests.test_engineering_retrieval import publish
from tests.test_langfuse_tracing import FakeClient, FakeHandler, _configured
from tests.test_openrouter_client import MODEL, _recording_client


def property_record(session, version):
    return add_property(
        session,
        version.id,
        PropertyIn(
            block_id="row-1",
            kind="E_MPa",
            original_unit="MPa",
            original_value=2000,
            value_basis="mean",
            standard_or_model="TEST P2",
            material_grade="P2",
            thickness_mm=18,
            page_section="p. 1 Properties",
            conditions={"service": "dry only"},
        ),
    )


@pytest.mark.parametrize("change", ["local_only", "revoked", "disabled"])
def test_late_rights_boundary_excludes_text_and_properties_on_gateway_wire(
    db_session,
    tmp_path,
    fake_embedder,
    settings,
    change,
):
    version = publish(db_session, tmp_path, remote=change != "local_only")
    prop = property_record(db_session, version)
    identifier = f"{version.id}:row-1"
    original = [
        HumanMessage("Is the shelf safe?"),
        AIMessage(
            "",
            tool_calls=[tool_call("search_engineering_knowledge", {"query": "TEST"})],
        ),
        ToolMessage(
            "Forbidden original: 2000 MPa dry only",
            tool_call_id="call-search_engineering_knowledge",
            additional_kwargs={
                "engineering": True,
                "engineering_source": True,
                "engineering_evidence_ids": [identifier],
            },
        ),
    ]
    if change == "revoked":
        decide_rights(
            db_session,
            version.id,
            RightsIn(
                action="revoke",
                evidence="Fixture rights withdrawn",
                reviewer="fixture author",
            ),
        )
    safe = request_history(
        db_session, original, engineering=True, enabled=change != "disabled"
    )
    sink = {}
    build_chat_model(
        settings, model_id=MODEL, http_client=_recording_client(sink)
    ).invoke(safe)
    wire = json.dumps(sink["body"])
    assert all(
        value not in wire
        for value in ("2000", "dry only", str(prop.id), "Forbidden original")
    )
    assert "ineligible" in wire
    assert "2000" in original[-1].content  # Local history was not destructively edited.


def test_fresh_packet_replaces_truncated_history_and_summary_is_never_evidence(
    db_session, tmp_path, fake_embedder
):
    version = publish(db_session, tmp_path)
    property_record(db_session, version)
    marked = ToolMessage(
        "2000…",
        tool_call_id="q",
        additional_kwargs={
            "engineering": True,
            "engineering_source": True,
            "engineering_evidence_ids": [f"{version.id}:row-1"],
        },
    )
    safe = request_history(
        db_session,
        [HumanMessage("engineering strength"), marked],
        engineering=True,
        enabled=True,
    )
    assert "dry only" in safe[-1].content and "2000…" not in safe[-1].content
    assert "2000" not in transcript([marked], tool_result_chars=4)
    assert "re-fetch" in transcript([marked])
    with pytest.raises(BudgetRefused):
        prepare(
            RequestBudget.for_model(
                MODEL, context_budget_tokens=100, max_output_tokens=20
            ),
            "fixed rules",
            safe,
        )
    assert marked.content == "2000…"


def test_typed_renderer_rejects_model_claims_and_keeps_units_conditions_citations(
    db_session, tmp_path, fake_embedder
):
    version = publish(db_session, tmp_path)
    prop = property_record(db_session, version)
    identifier = f"{version.id}:row-1"
    valid = json.dumps(
        {
            "evidence_ids": [identifier],
            "property_ids": [str(prop.id)],
            "owner_assumptions": ["18 mm"],
        }
    )
    rendered = render_answer(
        valid, db_session, [identifier], "18 mm shelf safe?", enabled=True
    )
    assert all(
        value in rendered
        for value in (
            "NOT VERIFIED",
            "not implemented",
            "2000.0 MPa",
            "dry only",
            "pages [1]",
            "basis mean",
            "unverified",
        )
    )
    for invalid in (
        "safe for 100 kg",
        '{"verified": true}',
        '{"property_ids": ["made-up"]}',
        '{"owner_assumptions": ["P3"]}',
    ):
        rejected = render_answer(
            invalid, db_session, [identifier], "18 mm shelf", enabled=True
        )
        assert (
            "NOT VERIFIED" in rejected
            and "rejected" in rejected
            and "100 kg" not in rejected
        )


@pytest.mark.parametrize(
    ("question", "required"),
    [
        ("wall cabinet hanger", "wall substrate"),
        ("TV child climb tipping", "child-climbing"),
        ("quartz countertop", "cutout"),
        ("Murphy bed safe", "qualified review"),
    ],
)
def test_hazard_gates_are_required_even_with_visual_approval(question, required):
    assert required in "; ".join(missing_inputs(question + "; render approved"))


def test_standalone_engineering_routes_to_researcher_and_rejects_unsafe_prose(
    tool_state,
):
    models = fake_models(
        foreman={"decisions": [{"specialist": "reviewer", "reason": "wrong"}]},
        researcher={"replies": ["safe for 100 kg"]},
    )
    harness = make_harness(tool_state, models, room=None)
    result = harness.turn("What load capacity can a shelf carry?")
    assert result["specialist"] == "researcher"
    assert "NOT VERIFIED" in result["messages"][-1].content
    assert "safe for 100 kg" not in result["messages"][-1].content
    assert models["reviewer"].calls == 0 and tool_state.launched == []


def test_engineering_revision_stays_designer_and_visual_discrepancy_stays_reviewer(
    tool_state,
):
    from tests.test_foreman import _bind_piece

    models = fake_models(
        foreman={
            "decisions": [
                {"specialist": "researcher", "reason": "capacity"},
                {"specialist": "reviewer", "reason": "image"},
            ]
        },
        designer={"replies": ["{}"]},
        reviewer={"replies": ["Visual discrepancy only."]},
    )
    harness = make_harness(tool_state, models)
    _bind_piece(tool_state, harness, screenshot=True)
    revision = harness.turn("Change the bench for greater load capacity")
    assert revision["specialist"] == "designer" and revision["engineering_turn"]
    assert "NOT VERIFIED" in revision["messages"][-1].content
    visual = harness.turn("The render shows the wrong width; compare against the spec")
    assert visual["specialist"] == "reviewer" and not visual["engineering_turn"]
    assert visual["messages"][-1].content == "Visual discrepancy only."


def test_disabled_guideline_adapter_cannot_consult_legacy_store(
    tool_state, monkeypatch
):
    from app.agent.tools import loaded_plugins
    from app.agent.tools.base import ToolContext, ToolDeps

    tools = loaded_plugins().builtin_tools()
    ctx = ToolContext(
        deps=ToolDeps(tool_state),
        owner_id=None,
        engineering_turn=True,
        engineering_enabled=False,
    )
    result = tools["search_guidelines"].run({"query": "shelf capacity"}, ctx)
    assert (
        isinstance(result, str) and "unavailable" in result and "NOT VERIFIED" in result
    )


def test_plugin_uses_current_context_and_records_separate_evidence_ids(
    tool_state, fake_embedder, tmp_path
):
    with Session(tool_state.engine) as session:
        version = publish(session, tmp_path)
        session.commit()
        identifier = f"{version.id}:row-1"
    try:
        models = fake_models(
            foreman={"decisions": [{"specialist": "researcher", "reason": "evidence"}]},
            researcher={
                "steps": [
                    [
                        tool_call(
                            "search_engineering_knowledge",
                            {"query": "TEST board", "mode": "keyword"},
                        )
                    ],
                    json.dumps({"evidence_ids": [identifier]}),
                ]
            },
        )
        harness = make_harness(tool_state, models, room=None)
        with Session(tool_state.engine) as session:
            from app.agent.tools import loaded_plugins

            plugins = loaded_plugins()
            set_global_enabled(session, "engineering_knowledge", True)
            set_thread_enabled(
                session, plugins, harness.thread, "engineering_knowledge", True
            )
            session.commit()
        result = harness.turn("TEST board elasticity and load capacity?")
        assert (
            "Evidence:" in result["messages"][-1].content
            and "NOT VERIFIED" in result["messages"][-1].content
        )
        assert "search_catalog_knowledge" not in models["researcher"].bound_tools
        with Session(tool_state.engine) as session:
            uses = session.scalars(
                select(EngineeringEvidenceUse).where(
                    EngineeringEvidenceUse.thread_id == harness.thread
                )
            ).all()
            assert len(uses) == 1 and uses[0].qualifications["pages"] == [1]
    finally:
        with Session(tool_state.engine) as session:
            set_global_enabled(session, "engineering_knowledge", False)
            session.execute(text("TRUNCATE knowledge_sources CASCADE"))
            session.commit()


def test_engineering_trace_exports_only_allowlisted_metrics_and_outcome(detach_tracing):
    class Exporter(FakeClient):
        def __init__(self):
            super().__init__()
            self.events = []

        def create_event(self, **fields):
            self.events.append(fields)

    exporter = Exporter()
    tracing = detach_tracing(
        Tracing(_configured(), handler_factory=lambda _: (exporter, FakeHandler()))
    )
    secret = "Restricted source 2000 MPa and equation; failed source excerpt"
    with tracing.turn(
        owner_id="opaque-owner",
        session_id="opaque-thread",
        input={"prompt": secret},
        suppress_content=True,
    ) as (config, trace_id):
        assert config["callbacks"] == [] and trace_id
        tracing.record_output(
            SimpleNamespace(
                reply=secret, failure_class=None, trace_content_suppressed=True
            )
        )
        tracing.record_engineering_usage(
            model_id=MODEL,
            trace_id=trace_id,
            duration_ms=20,
            input_tokens=5,
            output_tokens=3,
            prompt=secret,
            tool=secret,
            error=secret,
        )
    exported = repr((exporter.opened_with, exporter.updates, exporter.events))
    assert (
        secret not in exported and "input_tokens" in exported and "answered" in exported
    )
    assert exporter.opened_with["input"] is None
    assert (
        mask_personal_data(data={"state": {"engineering_turn": True}, "error": secret})
        == "[engineering content omitted]"
    )
