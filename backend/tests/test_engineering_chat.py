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
from app.engineering.chat import (
    SHORT_STATUS,
    engineering_intent,
    missing_inputs,
    render_answer,
    request_history,
    revision_engineering,
)
from app.engineering.registry import add_property, decide_rights
from app.engineering.schemas import PropertyIn, RightsIn
from app.observability.langfuse import Tracing, mask_personal_data
from app.plugins.enablement import set_global_enabled
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
    assert rendered.startswith(SHORT_STATUS)
    assert all(
        value in rendered
        for value in (
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
        assert rejected == SHORT_STATUS


def test_the_status_is_one_short_sentence_without_the_old_block(db_session):
    assert len(SHORT_STATUS.split()) <= 20
    rendered = render_answer(
        "{}", db_session, [], "Can this shelf hold 30 kg?", enabled=False
    )
    assert rendered == SHORT_STATUS
    for gone in (
        "not implemented",
        "Preliminary design advice",
        "switched off",
        "Missing inputs",
        "Legal/standard",
    ):
        assert gone not in rendered


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
    assert result["messages"][-1].content == SHORT_STATUS
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
    assert SHORT_STATUS in revision["messages"][-1].content
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
            set_global_enabled(session, "engineering_knowledge", True)
            session.commit()
        result = harness.turn("TEST board elasticity and load capacity?")
        assert (
            "Evidence:" in result["messages"][-1].content
            and result["messages"][-1].content.startswith(SHORT_STATUS)
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


# --- an answered engineering question does not loop (conversation-recent-inputs) -------------------


def _looping_thread() -> list:
    """The murphy bed thread's shape, as stored: the question unmarked, its reply marked."""


    return [
        HumanMessage("Describe the dividers.", id="h1"),
        AIMessage("bridge-dividers: 4 × 614 × 360 × 18 mm", id="a1"),
        HumanMessage("Will the bridge be structurally stable if the dividers are removed?", id="h2"),
        AIMessage(SHORT_STATUS, id="a2", additional_kwargs={"engineering": True}),
        HumanMessage("Keep and shorten the dividers.", id="h3"),
    ]


@pytest.mark.parametrize("routing", [True, False])
def test_an_answered_engineering_question_is_left_out_of_later_requests(routing: bool) -> None:


    stored = _looping_thread()
    sent = request_history(None, stored, engineering=False, enabled=False, routing=routing)
    ids = [m.id for m in sent]
    assert ids == ["h1", "a1", "h3"]  # the question and its status reply are both gone
    assert all(SHORT_STATUS not in str(m.content) for m in sent)
    assert [m.id for m in stored] == ["h1", "a1", "h2", "a2", "h3"]  # stored history unchanged
    assert not stored[2].additional_kwargs  # nothing written onto the owner's message


def test_the_current_engineering_question_is_still_sent() -> None:
    stored = [*_looping_thread()[:3]]
    sent = request_history(None, stored, engineering=True, enabled=False)
    assert [m.id for m in sent] == ["h2"]


def test_a_new_engineering_question_after_an_answered_one_is_still_one() -> None:
    from app.engineering.chat import engineering_intent

    assert engineering_intent("Can the shelf carry 30 kg?")
    assert not engineering_intent("Keep and shorten the dividers.")


# --- conversation-continuity ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "revision"),
    [
        ("Yes, please add a wall hanger to the sideboard", False),
        ("add a hinge to the left door", False),
        ("make the drawer 20 mm deeper", False),
        ("add a wall hanger that holds 30 kg", True),
        ("Change the bench for greater load capacity", True),
        ("make it safe to climb", True),
    ],
)
def test_hardware_words_alone_do_not_make_a_revision_engineering(text: str, revision: bool) -> None:
    assert revision_engineering(text) is revision


@pytest.mark.parametrize(
    "text",
    [
        "What's the allowable shelf span for particle boards?",
        "What shelf span is fine for 18 mm birch?",
        "How do I avoid sagging shelves?",
        "Will the shelf sag?",
        "add a wall hanger to the sideboard",
        "Wie viel darf das Regal durchhängen?",
    ],
)
def test_span_sag_and_hardware_are_engineering_by_code(text: str) -> None:
    assert engineering_intent(text)


@pytest.mark.parametrize("text", ["a sage green sideboard", "How much space is there between the bed and wall 1?"])
def test_ordinary_wording_is_not_engineering(text: str) -> None:
    assert not engineering_intent(text)


def test_a_revision_naming_hardware_goes_to_the_designer_as_an_ordinary_turn(tool_state) -> None:
    from tests.test_foreman import _bind_piece

    models = fake_models(
        foreman={"decisions": [{"specialist": "designer", "reason": "revision"}]},
        designer={"replies": ["Here is the change: add a wall hanger. Anything else?"]},
    )
    harness = make_harness(tool_state, models)
    _bind_piece(tool_state, harness, screenshot=False)
    state = harness.turn("Yes, please add a wall hanger to the sideboard")
    assert state["specialist"] == "designer" and not state["engineering_turn"]
    assert state["messages"][-1].content == "Here is the change: add a wall hanger. Anything else?"


def test_a_model_only_flag_is_answered_once_more_as_an_ordinary_turn(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [{"specialist": "researcher", "reason": "space", "engineering_question": True}]},
        researcher={"replies": ["The gap is about 1 m.", "The gap is 4350 mm minus the bed's width."]},
    )
    harness = make_harness(tool_state, models)
    state = harness.turn("How much space is there between the murphy bed and wall 1?")
    assert state["messages"][-1].content == "The gap is 4350 mm minus the bed's width."
    assert not state["engineering_turn"] and state["engineering_retried"]
    assert models["researcher"].calls == 2
    contents = [m.content for m in harness.snapshot().values["messages"]]
    assert SHORT_STATUS not in contents and "The gap is about 1 m." not in contents


def test_a_load_question_keeps_the_status_and_is_not_retried(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [{"specialist": "researcher", "reason": "load", "engineering_question": True}]},
        researcher={"replies": ["safe for 40 kg", "Yes, it is fine."]},
    )
    harness = make_harness(tool_state, models, room=None)
    state = harness.turn("Is the shelf safe for 40 kg?")
    assert state["messages"][-1].content == SHORT_STATUS
    assert models["researcher"].calls == 1
