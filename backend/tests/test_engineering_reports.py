import json
from dataclasses import replace
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.tools.base import ToolContext, ToolDeps
from app.db.models import (
    EngineeringAssessment,
    EngineeringCalculationReport,
    EngineeringMethodReview,
    PieceVersion,
    Thread,
)
from app.engineering.assessments import AssessmentIn
from app.engineering.chat import SHORT_STATUS, render_answer, request_history
from app.engineering.geometry import digest, part_domain, stored_geometry
from app.engineering.methods import method
from app.engineering.registry import (
    add_property,
    decide_rights,
    review_property,
)
from app.engineering.reports import (
    active_report_statuses,
    generate_report,
    report_copy,
    save_assessment,
    stale_reasons,
)
from app.engineering.schemas import PropertyIn, ReviewIn, RightsIn
from app.plugins.enablement import set_global_enabled
from plugins.engineering_calculators.tool import calculate, get_report, preview, record
from tests.api_helpers import desk
from tests.graph_helpers import fake_models, make_harness, place_in_room
from tests.test_engineering_retrieval import publish


@pytest.fixture
def piece(tool_state):
    root = tool_state.settings.render_root
    folder = root / "test-desk/v1"
    folder.mkdir(parents=True)
    document = desk()
    (folder / "input.json").write_text(json.dumps(document))
    with Session(tool_state.engine) as session:
        house_file.record_piece(session, "test-desk", "TEST desk")
        house_file.record_version(session, "test-desk", 1)
        thread = house_file.create_thread(
            session, "TEST assessment", package_id="test-desk"
        )
        house_file.add_build(session, thread.id, "test-desk")
        session.commit()
        thread_id = thread.id
    return "test-desk", thread_id


def inputs(**changes):
    return AssessmentIn.model_validate(
        {
            "version": 1,
            "furniture": "wall_cabinet",
            "bindings": [
                {"part_id": "cabinet-shelf", "load": {"value": 10, "unit": "kg"}}
            ],
            **changes,
        }
    )


def saved(session, root, piece, data=None):
    return save_assessment(
        session,
        root,
        piece[0],
        data or inputs(),
        owner_id=uuid4(),
        thread_id=piece[1],
        confirmed=True,
    )


def test_owner_confirmation_is_separate_from_geometry_and_no_model_fact_can_self_confirm(
    tool_state, piece
):
    ctx = ToolContext(
        deps=ToolDeps(tool_state),
        owner_id=uuid4(),
        thread_id=piece[1],
        package_id=piece[0],
        engineering_turn=True,
        calculators_enabled=True,
    )
    data = inputs().model_dump(mode="json")
    before = (tool_state.settings.render_root / "test-desk/v1/input.json").read_bytes()
    proposed = preview(data, ctx)
    assert (
        proposed.subject == "assessment_inputs"
        and "owner estimates" in proposed.summary
    )
    assert "confirmation" in record(data, ctx)
    with Session(tool_state.engine) as session:
        assert (
            session.scalar(
                select(EngineeringAssessment).where(
                    EngineeringAssessment.package_id == piece[0]
                )
            )
            is None
        )
    assert "snapshot" in record(data, replace(ctx, approved=True)).text
    assert (
        before
        == (tool_state.settings.render_root / "test-desk/v1/input.json").read_bytes()
    )
    assert tool_state.launched == []
    with Session(tool_state.engine) as session:
        assert session.get(PieceVersion, (piece[0], 1)).approved_at is None


def test_immutable_report_snapshot_and_reproducible_unavailable_results(
    tool_state, piece
):
    with Session(tool_state.engine) as session:
        assessment = saved(session, tool_state.settings.render_root, piece)
        first, second = (
            generate_report(session, tool_state.settings.render_root, assessment),
            generate_report(session, tool_state.settings.render_root, assessment),
        )
        assert first.report == second.report and first.input_hash == second.input_hash
        assert (
            first.report["overall"] == "INCOMPLETE"
            and first.report["conformity"] == "NOT_ESTABLISHED"
        )
        assert all(
            check["status"] == "NOT_VERIFIED" and check["result"] is None
            for check in first.report["checks"]
        )
        assert assessment.snapshot["canonical_loads"]["cabinet-shelf"][
            "value"
        ] == pytest.approx(98.1)
        session.commit()
        for model, identifier, field in (
            (EngineeringCalculationReport, first.id, "report"),
            (EngineeringAssessment, assessment.id, "snapshot"),
        ):
            with pytest.raises(DBAPIError), session.begin_nested():
                session.execute(
                    update(model)
                    .where(model.id == identifier)
                    .values({field: {"fake": "SAFE"}})
                )


def test_report_stales_after_geometry_facts_property_or_rights_change(
    tool_state, piece, fake_embedder, tmp_path
):
    with Session(tool_state.engine) as session:
        version = publish(session, tmp_path)
        prop = add_property(
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
                page_section="p. 1",
                conditions={"service": "dry only"},
            ),
        )
        data = inputs(
            bindings=[
                {
                    "part_id": "cabinet-shelf",
                    "standard_or_model": "TEST P2",
                    "material_grade": "P2",
                    "thickness_mm": 18,
                    "property_ids": [str(prop.id)],
                }
            ]
        )
        assessment = saved(session, tool_state.settings.render_root, piece, data)
        report = generate_report(session, tool_state.settings.render_root, assessment)
        session.commit()
        original = json.dumps(report.report, sort_keys=True)
        assert stale_reasons(session, tool_state.settings.render_root, assessment) == []
        review_property(
            session, prop.id, ReviewIn(reviewer="fixture reviewer", status="verified")
        )
        assert any(
            "properties" in reason
            for reason in stale_reasons(
                session, tool_state.settings.render_root, assessment
            )
        )
        saved(session, tool_state.settings.render_root, piece, inputs())
        assert any(
            "facts" in reason
            for reason in stale_reasons(
                session, tool_state.settings.render_root, assessment
            )
        )
        house_file.record_version(session, piece[0], 2)
        assert any(
            "geometry" in reason
            for reason in stale_reasons(
                session, tool_state.settings.render_root, assessment
            )
        )
        decide_rights(
            session,
            version.id,
            RightsIn(action="revoke", reviewer="fixture author", evidence="withdrawn"),
        )
        copy = report_copy(
            session, tool_state.settings.render_root, report.id, remote=True
        )
        assert (
            copy["stale"]
            and copy["evidence_unavailable"]
            and "2000" not in json.dumps(copy)
        )
        assert original == json.dumps(report.report, sort_keys=True)
        # Audit source rows are test-only and independent of piece deletion.
        session.rollback()
        session.execute(text("TRUNCATE knowledge_sources CASCADE"))
        session.commit()


def test_local_only_report_properties_and_legacy_derivation_text_never_cross_cloud_boundary(
    tool_state, piece, fake_embedder, tmp_path, settings
):
    from app.agent.models.openrouter_client import build_chat_model
    from tests.test_openrouter_client import MODEL, _recording_client

    with Session(tool_state.engine) as session:
        version = publish(session, tmp_path, remote=False)
        prop = add_property(
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
                page_section="p. 1",
            ),
        )
        assessment = saved(
            session,
            tool_state.settings.render_root,
            piece,
            inputs(
                bindings=[{"part_id": "cabinet-shelf", "property_ids": [str(prop.id)]}]
            ),
        )
        report = generate_report(session, tool_state.settings.render_root, assessment)
        message = ToolMessage(
            "local report excerpt 2000 MPa",
            tool_call_id="report",
            additional_kwargs={
                "engineering": True,
                "engineering_report_ids": [str(report.id)],
            },
        )
        safe = request_history(
            session,
            [HumanMessage("engineering capacity"), message],
            engineering=True,
            enabled=True,
            render_root=tool_state.settings.render_root,
        )
        sink = {}
        build_chat_model(
            settings, model_id=MODEL, http_client=_recording_client(sink)
        ).invoke(safe)
        assert "2000" not in json.dumps(sink["body"]) and "ineligible" in json.dumps(
            sink["body"]
        )
        assert "2000" in message.content


def test_geometry_domain_retains_derivation_and_rejects_partial_dividers_folds_and_unknown_parts(
    tool_state, piece
):
    geometry = stored_geometry(tool_state.settings.render_root, piece[0], 1)
    assert part_domain(geometry, "missing-shelf")
    copy = json.loads(json.dumps(geometry))
    copy["spec"]["modules"][0]["divider_spans"] = [{"from": "bottom", "to": "shelf-1"}]
    assert "support/joint" in part_domain(copy, "cabinet-shelf")[0]
    copy["spec"]["modules"][0].pop("divider_spans")
    copy["spec"]["modules"][0]["side_folds"] = [{"angle_deg": 45}]
    assert "folded/polygonal" in part_domain(copy, "cabinet-shelf")[0]
    assert digest(geometry["parts"]) == digest(
        stored_geometry(tool_state.settings.render_root, piece[0], 1)["parts"]
    )


def test_conversation_deletion_retains_reports_and_piece_deletion_uses_existing_cascade(
    tool_state, piece, monkeypatch
):
    from app.blender import storage

    root = tool_state.settings.render_root
    with Session(tool_state.engine) as session:
        assessment = saved(session, root, piece)
        report = generate_report(session, root, assessment)
        session.commit()
        report_id = report.id
        session.execute(delete(Thread).where(Thread.id == piece[1]))
        session.commit()
        session.expire_all()
        assert session.get(EngineeringCalculationReport, report_id).thread_id is None
        assert session.get(EngineeringAssessment, assessment.id).thread_id is None

        def fail(*args):
            raise OSError("test folder rename failure")

        with monkeypatch.context() as patch:
            patch.setattr(storage, "move_version_aside", fail)
            with pytest.raises(OSError):
                house_file.delete_version(session, root, piece[0], 1)
        assert session.get(EngineeringCalculationReport, report_id) is not None
        house_file.delete_version(session, root, piece[0], 1)
        session.expire_all()
        assert session.get(EngineeringCalculationReport, report_id) is None


def test_record_deletion_failure_keeps_reports_and_restores_the_folder(
    tool_state, piece, monkeypatch
):
    root = tool_state.settings.render_root
    with Session(tool_state.engine) as session:
        assessment = saved(session, root, piece)
        report = generate_report(session, root, assessment)
        session.commit()
        report_id = report.id

        def fail():
            raise RuntimeError("test commit failure")

        with monkeypatch.context() as patch:
            patch.setattr(session, "commit", fail)
            with pytest.raises(RuntimeError):
                house_file.delete_version(session, root, piece[0], 1)
        session.rollback()
        assert session.get(EngineeringCalculationReport, report_id) is not None
        assert (root / piece[0] / "v1").is_dir()


def test_active_piece_memory_contains_ids_status_only_and_other_piece_report_is_absent(
    tool_state, piece
):
    root = tool_state.settings.render_root
    with Session(tool_state.engine) as session:
        report = generate_report(session, root, saved(session, root, piece))
        session.commit()
        statuses = active_report_statuses(session, root, piece[0])
        assert statuses[0]["report_id"] == str(
            report.id
        ) and "snapshot" not in json.dumps(statuses)
        assert active_report_statuses(session, root, "other-piece") == []
        assert report_copy(session, root, report.id, package_id="other-piece") is None


def test_method_disable_marks_current_report_stale_without_rewriting_history(
    tool_state, piece
):
    root = tool_state.settings.render_root
    with Session(tool_state.engine) as session:
        assessment = saved(session, root, piece)
        report = generate_report(session, root, assessment)
        original = json.dumps(report.report, sort_keys=True)
        selected = method("shelf_immediate")
        review = EngineeringMethodReview(
            method_id=selected.id,
            method_version=selected.version,
            definition_hash=digest(selected.definition),
            action="disable",
            reviewer="synthetic reviewer",
            qualification_evidence="test only; no real qualification",
            evidence="test rollback",
        )
        session.add(review)
        session.commit()
        assert any(
            "methods" in reason for reason in stale_reasons(session, root, assessment)
        )
        assert json.dumps(report.report, sort_keys=True) == original
        with pytest.raises(DBAPIError), session.begin_nested():
            session.execute(
                update(EngineeringMethodReview)
                .where(EngineeringMethodReview.id == review.id)
                .values(action="accept")
            )
        # Append-only method audit belongs to the isolated test database.
        session.execute(text("TRUNCATE engineering_method_reviews"))
        session.commit()


def test_calculate_fetch_and_typed_renderer_use_code_report_and_refuse_disabled_arithmetic(
    tool_state, piece
):
    ctx = ToolContext(
        deps=ToolDeps(tool_state),
        owner_id=uuid4(),
        thread_id=piece[1],
        package_id=piece[0],
        engineering_turn=True,
        calculators_enabled=True,
    )
    root = tool_state.settings.render_root
    with Session(tool_state.engine) as session:
        assessment = saved(session, root, piece)
        session.commit()
        identifier = str(assessment.id)
    output = calculate({"assessment_id": identifier}, ctx)
    report_id = output.update["engineering_report_ids"][0]
    assert "INCOMPLETE" in output.text and "NOT_ESTABLISHED" in output.text
    assert get_report({"report_id": report_id}, ctx).update == output.update
    assert "outside" in calculate(
        {"assessment_id": identifier}, replace(ctx, package_id="other-piece")
    )
    assert "outside" in get_report(
        {"report_id": report_id}, replace(ctx, package_id="other-piece")
    )
    disabled = replace(ctx, calculators_enabled=False)
    for tool, args in (
        (calculate, {"assessment_id": identifier}),
        (get_report, {"report_id": report_id}),
    ):
        assert (
            tool(args, disabled)
            == "Engineering calculation tool is unavailable; NOT VERIFIED."
        )
    with Session(tool_state.engine) as session:
        raw = json.dumps({"report_ids": [report_id]})
        rendered = render_answer(
            raw,
            session,
            [],
            "engineering capacity",
            enabled=False,
            report_ids=[report_id],
            calculators_enabled=True,
            render_root=root,
        )
        assert "code-generated" in rendered and '"overall": "INCOMPLETE"' in rendered
        assert "98.1" in rendered and "approved_at" not in rendered
        rejected = render_answer(
            raw,
            session,
            [],
            "engineering capacity",
            enabled=False,
            report_ids=[report_id],
            calculators_enabled=False,
            render_root=root,
        )
        assert rejected == SHORT_STATUS
        assert session.get(PieceVersion, (piece[0], 1)).approved_at is None
    assert tool_state.launched == []


@pytest.mark.parametrize("answer", ["yes", "no"])
def test_assessment_confirmation_through_graph_requires_explicit_owner_answer(
    tool_state, piece, answer
):

    models = fake_models(
        foreman={"decisions": [{"specialist": "researcher", "reason": "assessment"}]},
        researcher={
            "steps": [
                [
                    {
                        "name": "record_assessment_inputs",
                        "args": inputs().model_dump(mode="json"),
                        "id": "assessment",
                        "type": "tool_call",
                    }
                ],
                "{}",
            ]
        },
    )
    harness = make_harness(tool_state, models)
    harness.start(piece[0])
    place_in_room(harness, piece[0])
    with Session(tool_state.engine) as session:
        set_global_enabled(session, "engineering_calculators", True)
        session.commit()
    pending = harness.turn("Record engineering loads for this shelf")
    assert pending["__interrupt__"][0].value["subject"] == "assessment_inputs"
    harness.answer(answer)
    with Session(tool_state.engine) as session:
        assessment = session.scalar(
            select(EngineeringAssessment).where(
                EngineeringAssessment.package_id == piece[0]
            )
        )
        assert (assessment is not None) == (answer == "yes")
        if assessment is not None:
            assert assessment.snapshot["inputs"]["bindings"][0]["load"] == {
                "value": 10.0,
                "unit": "kg",
            }
        assert session.get(PieceVersion, (piece[0], 1)).approved_at is None
    assert tool_state.launched == []


def test_report_memory_is_opaque_and_request_copies_restore_full_conditions(
    tool_state, piece
):
    from app.agent.summaries import transcript

    root = tool_state.settings.render_root
    with Session(tool_state.engine) as session:
        report = generate_report(
            session,
            root,
            saved(
                session,
                root,
                piece,
                inputs(owner_assumptions=["fixture assumption dry installation only"]),
            ),
        )
        marker = ToolMessage(
            "compressed misleading memory SAFE 100 kg",
            tool_call_id="report",
            additional_kwargs={
                "engineering": True,
                "engineering_report_ids": [str(report.id)],
            },
        )
        compressed = transcript([marker])
        assert str(report.id) in compressed and "100 kg" not in compressed
        copied = request_history(
            session,
            [HumanMessage("engineering capacity"), marker],
            engineering=True,
            enabled=False,
            render_root=root,
        )
        payload = str(copied[-1].content)
        assert (
            "dry installation only" in payload
            and "INCOMPLETE" in payload
            and "NOT_VERIFIED" in payload
        )
        assert (
            "SAFE 100 kg" not in payload
            and marker.content == "compressed misleading memory SAFE 100 kg"
        )


def test_shelf_immediate_runs_only_when_enabled_and_inside_its_domain(
    tool_state, piece, fake_embedder, tmp_path
):
    root = tool_state.settings.render_root
    with Session(tool_state.engine) as session:
        version = publish(session, tmp_path)
        prop = add_property(
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
                page_section="p. 1",
                conditions={"service": "dry only"},
            ),
        )
        review_property(
            session, prop.id, ReviewIn(reviewer="fixture reviewer", status="verified")
        )

        def check(**binding):
            data = inputs(
                bindings=[
                    {
                        "part_id": "cabinet-shelf",
                        "standard_or_model": "TEST P2",
                        "material_grade": "P2",
                        "thickness_mm": 18,
                        "property_ids": [str(prop.id)],
                        "load": {"value": 5, "unit": "kg/m"},
                        "support": "simply_supported",
                        "support_positions": [0, 0.964],
                        "support_path": "shelf pins in both sides",
                        **binding,
                    }
                ]
            )
            report = generate_report(session, root, saved(session, root, piece, data))
            return next(
                item
                for item in report.report["checks"]
                if item["method_id"] == "shelf_immediate"
            )

        # Complete, in-domain inputs stay unverified until a review accepts the method.
        assert check()["status"] == "NOT_VERIFIED" and check()["result"] is None
        selected = method("shelf_immediate")
        session.add(
            EngineeringMethodReview(
                method_id=selected.id,
                method_version=selected.version,
                definition_hash=digest(selected.definition),
                action="accept",
                reviewer="synthetic reviewer",
                qualification_evidence="test only; no real qualification",
                evidence="test acceptance",
            )
        )
        session.flush()
        # 49.05 N/m over 964 mm on 288 x 18 mm, E 2000 MPa: about 1.97 mm, under L/400.
        light = check()
        assert light["status"] == "PASS_FOR_STATED_CASE"
        assert light["unit"] == "m/m" and light["limit"] == pytest.approx(1 / 400)
        assert "1.97 mm" in light["case"] and "strength" in light["case"]
        heavy = check(load={"value": 30, "unit": "kg/m"})
        assert heavy["status"] == "FAIL_FOR_STATED_CASE" and heavy["utilisation"] > 1
        for binding, reason in (
            ({"load": {"value": 10, "unit": "kg"}}, "uniform load"),
            ({"support": "cantilever"}, "simply supported"),
            ({"support_positions": [0, 0.5, 0.964]}, "two end supports"),
            ({"support_positions": [0, 1.2]}, "within the shelf length"),
            ({"property_ids": []}, "property"),
        ):
            refused = check(**binding)
            assert refused["status"] == "NOT_VERIFIED" and refused["result"] is None
            assert any(reason in item for item in refused["missing_inputs"])
        session.rollback()
        session.execute(text("TRUNCATE engineering_method_reviews"))
        session.execute(text("TRUNCATE knowledge_sources CASCADE"))
        session.commit()
