from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.engineering.assessments import (
    AssessmentIn,
    CalculationReport,
    CheckResult,
    Quantity,
)
from app.engineering.geometry import digest
from app.engineering.methods import (
    METHODS,
    Criterion,
    Method,
    allowable_property,
    compare_result,
    method,
    unavailable,
)
from app.engineering.registry import EvidenceRefused


def test_closed_registry_has_no_executable_user_formula_or_enabled_unreviewed_method():
    assert set(METHODS) == {
        "shelf_immediate",
        "shelf_creep",
        "joint",
        "hardware",
        "anchor",
        "tipping",
        "countertop",
        "murphy",
    }
    for item in METHODS.values():
        assert item.domain and item.units and item.required_inputs
        assert not item.releasable and unavailable(item.id).status == "NOT_VERIFIED"
        assert unavailable(item.id).result is None
    with pytest.raises(EvidenceRefused):
        method("__import__('os').system('touch /tmp/unsafe')")
    with pytest.raises(EvidenceRefused):
        method("shelf_immediate", "unknown revision")
    with pytest.raises(ValidationError):
        AssessmentIn(
            version=1, furniture="shelf", expression="width * thickness", confirmed=True
        )


def test_original_units_and_mass_conversion_are_explicit():
    converted = Quantity(value=10, unit="kg").force()
    assert converted["value"] == pytest.approx(98.1) and converted["unit"] == "N"
    assert (
        converted["original_value"] == 10
        and converted["original_unit"] == "kg"
        and converted["conversion_factor"] == 9.81
    )
    assert Quantity(value=1, unit="kN").force()["value"] == 1000
    assert Quantity(value=1000, unit="mm").canonical()["value"] == 1
    assert Quantity(value=1, unit="N/mm").canonical()["value"] == 1000
    with pytest.raises(ValueError):
        Quantity(value=18, unit="mm").force()
    with pytest.raises(ValueError):
        Quantity(value=1e308, unit="kg").force()


@pytest.mark.parametrize("value", [float("inf"), float("nan"), -1, 0])
def test_invalid_values_refused_before_arithmetic(value):
    with pytest.raises(ValidationError):
        Quantity(value=value, unit="N")


@pytest.mark.parametrize("basis", ["mean", "characteristic", "nominal", "unknown"])
def test_test_basis_is_never_allowable_resistance(basis):
    prop = SimpleNamespace(
        verification_status="verified",
        record={"kind": "capacity_N", "value_basis": basis, "value": 100},
    )
    with pytest.raises(EvidenceRefused) as error:
        allowable_property(prop, method("shelf_immediate"))
    assert error.value.field == "value_basis"


def test_range_unknown_and_unverified_never_gain_a_midpoint_or_safety_factor():
    for state, value in (("verified", None), ("unverified", 100)):
        prop = SimpleNamespace(
            verification_status=state,
            record={
                "kind": "capacity_N",
                "value_basis": "allowable",
                "value": value,
                "minimum": 100,
                "maximum": 200,
            },
        )
        with pytest.raises(EvidenceRefused):
            allowable_property(prop, method("shelf_immediate"))


def test_stiffness_is_not_allowable_resistance_even_with_a_mislabeled_basis():
    prop = SimpleNamespace(
        verification_status="verified",
        record={"kind": "E_MPa", "value_basis": "allowable", "value": 2000},
    )
    with pytest.raises(EvidenceRefused) as error:
        allowable_property(prop, method("shelf_immediate"))
    assert error.value.field == "kind"


def test_code_comparison_requires_exact_review_and_cited_criterion():
    # Original synthetic test contract; this is no released engineering method.
    selected = Method(
        "fixture_comparison",
        "test",
        ("N",),
        ("demand",),
        "synthetic test only",
        citation_evidence_ids=("fixture:criterion",),
        criteria=(Criterion("maximum", 100, "N", "fixture:criterion"),),
        independent_reference_cases=({"original_test_case": 100},),
        implementation=lambda demand: demand,
    )
    accepted = {
        "enabled": True,
        "qualified_review_state": "accept",
        "definition_hash": digest(selected.definition),
    }
    at_limit = compare_result(selected, accepted, 100, "maximum", part_id="test-part")
    above = compare_result(selected, accepted, 101, "maximum")
    assert at_limit.status == "PASS_FOR_STATED_CASE" and at_limit.utilisation == 1
    assert (
        at_limit.unit == "N"
        and at_limit.limit == 100
        and at_limit.source_evidence_ids == ["fixture:criterion"]
    )
    assert (
        above.status == "FAIL_FOR_STATED_CASE"
        and above.utilisation == pytest.approx(1.01)
    )
    for state, value, criterion in (
        ({}, 100, "maximum"),
        ({**accepted, "definition_hash": "old"}, 100, "maximum"),
        (accepted, 100, "unknown"),
        (accepted, float("inf"), "maximum"),
        (accepted, -1, "maximum"),
    ):
        check = compare_result(selected, state, value, criterion)
        assert (
            check.status == "NOT_VERIFIED"
            and check.result is None
            and check.missing_inputs
        )
    unreferenced = Method(
        "fixture_comparison",
        "test",
        ("N",),
        ("demand",),
        "synthetic test only",
        citation_evidence_ids=("fixture:other",),
        criteria=selected.criteria,
        independent_reference_cases=selected.independent_reference_cases,
        implementation=selected.implementation,
    )
    assert not unreferenced.releasable


@pytest.mark.parametrize("limit, unit", [(0, "N"), (float("nan"), "N"), (100, "")])
def test_criterion_cannot_be_unbounded_or_unitless(limit, unit):
    with pytest.raises(ValueError):
        Criterion("maximum", limit, unit, "fixture:criterion")


def test_omitted_assessment_facts_are_null_and_owner_confirmation_cannot_be_claimed():
    assessment = AssessmentIn(
        version=1, furniture="wall_cabinet", bindings=[{"part_id": "cabinet-shelf"}]
    )
    assert assessment.wall_substrate is None and assessment.duration is None
    assert (
        assessment.bindings[0].load is None and assessment.bindings[0].support is None
    )
    assert (
        assessment.bindings[0].material_grade is None
        and assessment.bindings[0].property_ids == []
    )
    with pytest.raises(ValidationError):
        AssessmentIn(
            version=1,
            furniture="shelf",
            bindings=[{"part_id": "shelf", "load": {"value": 18, "unit": "mm"}}],
        )
    with pytest.raises(ValidationError):
        AssessmentIn(
            version=1,
            furniture="entertainment_unit",
            tv_mass={"value": 100, "unit": "N"},
        )


def test_intermediate_without_criterion_cannot_pass_and_one_pass_cannot_approve_piece():
    with pytest.raises(ValidationError):
        CheckResult(
            method_id="shelf_immediate",
            method_version="1",
            status="PASS_FOR_STATED_CASE",
            result=1,
            unit="mm",
        )
    passing = CheckResult(
        method_id="shelf_immediate",
        method_version="test-only",
        status="PASS_FOR_STATED_CASE",
        result=1,
        unit="mm",
        limit=2,
        criterion="original synthetic test criterion",
        source_evidence_ids=["fixture:criterion"],
    )
    unresolved = unavailable("anchor")
    report = CalculationReport(
        checks=[passing, unresolved],
        overall="INCOMPLETE",
        assumptions=["synthetic test"],
        review_requirements=["anchor review"],
    )
    assert report.conformity == "NOT_ESTABLISHED"
    with pytest.raises(ValidationError):
        CalculationReport(
            checks=[passing, unresolved],
            overall="COMPLETE_FOR_STATED_CASES",
            assumptions=[],
            review_requirements=[],
        )


@pytest.mark.parametrize("updates", [{"unit": None}, {"limit": 0}, {"utilisation": -1}])
def test_report_values_cannot_lose_units_or_acquire_invalid_limits(updates):
    with pytest.raises(ValidationError):
        CheckResult.model_validate(
            {
                "method_id": "fixture",
                "method_version": "test",
                "status": "PASS_FOR_STATED_CASE",
                "result": 1,
                "unit": "mm",
                "limit": 2,
                "criterion": "original synthetic criterion",
                "source_evidence_ids": ["fixture:criterion"],
                **updates,
            }
        )
