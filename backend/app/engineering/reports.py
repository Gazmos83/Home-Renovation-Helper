"""Immutable owner-confirmed snapshots and rights-gated report copies."""

from uuid import UUID

from sqlalchemy import func, select

from app.db.models import (
    EngineeringAssessment,
    EngineeringCalculationReport,
    EngineeringMethodReview,
    EngineeringProperty,
    PieceVersion,
)
from app.engineering.assessments import AssessmentIn, CalculationReport
from app.engineering.geometry import digest, part_domain, stored_geometry
from app.engineering.methods import METHODS, method, unavailable
from app.engineering.registry import EvidenceRefused, current_rights
from app.engineering.retrieval import resolve_evidence


def method_state(session, identifier):
    selected = method(identifier)
    review = session.scalar(
        select(EngineeringMethodReview)
        .where(
            EngineeringMethodReview.method_id == selected.id,
            EngineeringMethodReview.method_version == selected.version,
        )
        .order_by(EngineeringMethodReview.sequence.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )
    return {
        "method_id": selected.id,
        "method_version": selected.version,
        "definition_hash": digest(selected.definition),
        "implemented": selected.implementation is not None,
        "review_id": str(review.id) if review else None,
        "qualified_review_state": review.action if review else "pending",
        "enabled": bool(
            selected.releasable
            and review
            and review.action == "accept"
            and review.definition_hash == digest(selected.definition)
        ),
    }


def capture_inputs(session, root, package_id, inputs: AssessmentIn) -> dict:
    if session.get(PieceVersion, (package_id, inputs.version)) is None:
        raise EvidenceRefused("version", "recorded piece version is required")
    geometry = stored_geometry(root, package_id, inputs.version)
    properties, evidence_ids = {}, set()
    for binding in inputs.bindings:
        for property_id in binding.property_ids:
            prop = session.get(EngineeringProperty, property_id, populate_existing=True)
            if prop is None:
                raise EvidenceRefused("property_id", "property revision is unavailable")
            evidence_id = f"{prop.version_id}:{prop.block_id}"
            packet = resolve_evidence(session, evidence_id, remote=False)
            if packet is None:
                raise EvidenceRefused(
                    "property_id",
                    "property has no currently eligible retained local evidence",
                )
            for field in ("standard_or_model", "material_grade", "thickness_mm"):
                value = getattr(binding, field)
                if value is not None and prop.record.get(field) != value:
                    raise EvidenceRefused(
                        field, "binding must match the exact property revision"
                    )
            properties[str(prop.id)] = {
                "record": prop.record,
                "verification_status": prop.verification_status,
                "reviewed_by": prop.reviewed_by,
                "evidence_id": evidence_id,
            }
            evidence_ids.add(evidence_id)
        evidence_ids.update(binding.manual_evidence_ids)
        if binding.load_distribution_evidence_id:
            evidence_ids.add(binding.load_distribution_evidence_id)
    for field in (
        "anchor_approval_evidence_id",
        "misuse_load_case_evidence_id",
        "countertop_manual_evidence_id",
        "mechanism_manual_evidence_id",
    ):
        if identifier := getattr(inputs, field):
            evidence_ids.add(identifier)
    evidence = {}
    for identifier in sorted(evidence_ids):
        packet = resolve_evidence(session, identifier, remote=False)
        if packet is None:
            raise EvidenceRefused(
                "evidence_id",
                "source has no currently eligible retained local evidence",
            )
        decision = current_rights(session, UUID(packet["version_id"]))
        evidence[identifier] = {
            "packet": packet,
            "rights_decision_id": str(decision.id),
        }
    return {
        "geometry": geometry,
        "inputs": inputs.model_dump(mode="json"),
        "canonical_loads": {
            binding.part_id: binding.load.force()
            if binding.load.unit in {"kg", "N", "kN"}
            else binding.distributed_load()
            for binding in inputs.bindings
            if binding.load is not None
        },
        "properties": properties,
        "evidence": evidence,
        "methods": {
            identifier: method_state(session, identifier) for identifier in METHODS
        },
        "assumptions_status": "Owner-confirmed estimates; not independently verified engineering facts",
    }


def save_assessment(
    session, root, package_id, inputs, *, owner_id, thread_id, confirmed: bool
):
    if not confirmed:
        raise EvidenceRefused("confirmation", "explicit owner confirmation is required")
    snapshot = capture_inputs(session, root, package_id, inputs)
    row = EngineeringAssessment(
        package_id=package_id,
        version=inputs.version,
        owner_id=owner_id,
        thread_id=thread_id,
        snapshot=snapshot,
        spec_hash=snapshot["geometry"]["spec_hash"],
        input_hash=digest(snapshot),
    )
    session.add(row)
    session.flush()
    return row


def assessment_for_piece(session, identifier, package_id):
    row = session.get(EngineeringAssessment, identifier, populate_existing=True)
    if row is None or row.package_id != package_id:
        raise EvidenceRefused("assessment_id", "assessment is outside the active piece")
    return row


def stale_reasons(session, root, assessment) -> list[str]:
    reasons = []
    latest_version = session.scalar(
        select(func.max(PieceVersion.version)).where(
            PieceVersion.package_id == assessment.package_id
        )
    )
    if latest_version != assessment.version:
        reasons.append("a newer geometry version exists")
    latest_assessment = session.scalar(
        select(EngineeringAssessment.id)
        .where(
            EngineeringAssessment.package_id == assessment.package_id,
            EngineeringAssessment.version == assessment.version,
        )
        .order_by(
            EngineeringAssessment.created_at.desc(),
            EngineeringAssessment.sequence.desc(),
        )
        .limit(1)
    )
    if latest_assessment != assessment.id:
        reasons.append("newer owner-confirmed facts or bindings exist")
    try:
        current = capture_inputs(
            session,
            root,
            assessment.package_id,
            AssessmentIn.model_validate(assessment.snapshot["inputs"]),
        )
        if current["geometry"]["spec_hash"] != assessment.spec_hash:
            reasons.append("stored geometry/derivation changed")
        for field in ("properties", "evidence", "methods"):
            if digest(current[field]) != digest(assessment.snapshot[field]):
                reasons.append(f"{field} revisions or rights/review state changed")
    except EvidenceRefused:
        reasons.append(
            "required geometry or retained source evidence is unavailable/ineligible"
        )
    return reasons


def generate_report(session, root, assessment) -> EngineeringCalculationReport:
    snapshot = assessment.snapshot
    inputs = AssessmentIn.model_validate(snapshot["inputs"])
    stale = stale_reasons(session, root, assessment)
    checks = []
    for binding in inputs.bindings:
        missing = [*part_domain(snapshot["geometry"], binding.part_id), *stale]
        if (
            not binding.standard_or_model
            or not binding.material_grade
            or not binding.property_ids
        ):
            missing.append("exact reviewed product/grade/property bindings")
        if (
            binding.load is None
            or binding.support is None
            or not binding.support_positions
            or not binding.support_path
        ):
            missing.append("declared load distribution, support geometry and load path")
        checks.append(
            unavailable("shelf_immediate", part_id=binding.part_id, missing=missing)
        )
        checks.append(
            unavailable(
                "shelf_creep",
                part_id=binding.part_id,
                missing=[
                    "material-specific duration/moisture/creep evidence and sustained-load share",
                    *stale,
                ],
            )
        )
    if not inputs.bindings:
        checks.append(
            unavailable(
                "shelf_immediate",
                missing=[
                    "part bindings, loads, supports and reviewed properties",
                    *stale,
                ],
            )
        )
    checks.extend(
        [
            unavailable(
                "joint", missing=["exact joint/fastener geometry and load direction"]
            ),
            unavailable(
                "hardware",
                missing=[
                    "matching model/revision/orientation and documented load distribution"
                ],
            ),
        ]
    )
    requirements = [
        "Source-backed equations, criteria and independent reference cases require qualified method review before enabling calculations"
    ]
    if inputs.furniture in {
        "wall_cabinet",
        "murphy_bed",
        "kitchen_wall_cabinet",
        "kitchen_tall_cabinet",
    }:
        checks.append(
            unavailable(
                "anchor",
                missing=[
                    "identified wall substrate, exact anchor approval, embedment/edge/spacing and tension/shear load transfer",
                    "DIN EN 15939 does not verify wall fixings or substrate",
                ],
            )
        )
    if inputs.furniture == "entertainment_unit":
        checks.append(
            unavailable(
                "tipping",
                missing=[
                    "footprint, masses/centre of gravity, TV/accessory and foreseeable child-climbing load cases"
                ],
            )
        )
    if inputs.furniture in {
        "kitchen_base_cabinet",
        "kitchen_wall_cabinet",
        "kitchen_tall_cabinet",
        "kitchen_drawer",
    }:
        checks.append(
            unavailable(
                "tipping",
                missing=[
                    "cabinet self-weight, contents, footprint/centre of gravity and stability case"
                ],
            )
        )
    if inputs.furniture == "kitchen_drawer":
        checks.append(
            unavailable(
                "hardware",
                missing=[
                    "exact runner series/variant/revision, mounting geometry and declared load conditions",
                    "drawer self-weight, box joints and cabinet support; runner rating alone is insufficient",
                ],
            )
        )
    if inputs.furniture in {"countertop", "kitchen_worktop"}:
        checks.append(
            unavailable(
                "countertop",
                missing=[
                    "exact product/thickness/manual and reviewed overhang/cutout/support conditions"
                ],
            )
        )
    if inputs.furniture == "murphy_bed":
        checks.append(
            unavailable(
                "murphy",
                missing=[
                    "matching mechanism/manual revision, complete wall/anchor assessment and qualified crush/impact/deployment review"
                ],
            )
        )
        requirements.append(
            "No individual check can approve the whole Murphy bed or authorise installation"
        )
    report = CalculationReport(
        checks=checks,
        overall="INCOMPLETE",
        assumptions=inputs.owner_assumptions,
        review_requirements=requirements,
    )
    row = EngineeringCalculationReport(
        assessment_id=assessment.id,
        package_id=assessment.package_id,
        version=assessment.version,
        thread_id=assessment.thread_id,
        report=report.model_dump(mode="json"),
        spec_hash=assessment.spec_hash,
        input_hash=assessment.input_hash,
    )
    session.add(row)
    session.flush()
    return row


def report_copy(
    session, root, identifier, *, package_id=None, remote=False
) -> dict | None:
    row = session.get(EngineeringCalculationReport, identifier, populate_existing=True)
    if row is None or (package_id is not None and row.package_id != package_id):
        return None
    assessment = session.get(EngineeringAssessment, row.assessment_id)
    stale = stale_reasons(session, root, assessment)
    status = {
        "report_id": str(row.id),
        "assessment_id": str(assessment.id),
        "package_id": row.package_id,
        "version": row.version,
        "overall": row.report["overall"],
        "stale": bool(stale),
        "stale_reasons": stale,
        "conformity": "NOT_ESTABLISHED",
    }
    if any(
        resolve_evidence(session, evidence_id, remote=remote) is None
        for evidence_id in assessment.snapshot["evidence"]
    ):
        return {
            **status,
            "evidence_unavailable": True,
            "limitation": "Complete report content is currently ineligible for this request; NOT VERIFIED.",
        }
    output = {
        **status,
        "spec_hash": row.spec_hash,
        "input_hash": row.input_hash,
        "snapshot": assessment.snapshot,
        "report": row.report,
    }
    if remote:
        # Frozen legacy drilling/rule inputs have no engineering rights mapping.
        # Export only dimensional part data from that derivation, never its
        # datasheet/rule quotes. Registered engineering evidence is gated above.
        output["snapshot"] = {
            **assessment.snapshot,
            "geometry": {
                "spec_hash": assessment.spec_hash,
                "parts": [
                    {
                        key: value
                        for key, value in part.items()
                        if key in {"id", "qty", "l", "w", "t"}
                    }
                    for part in assessment.snapshot["geometry"]["parts"]
                ],
            },
        }
    return output


def active_report_statuses(session, root, package_id):
    rows = session.scalars(
        select(EngineeringCalculationReport)
        .where(EngineeringCalculationReport.package_id == package_id)
        .order_by(EngineeringCalculationReport.created_at.desc())
        .limit(5)
    )
    return [
        {
            key: value
            for key, value in report_copy(session, root, row.id).items()
            if key in {"report_id", "version", "overall", "stale", "conformity"}
        }
        for row in rows
    ]
