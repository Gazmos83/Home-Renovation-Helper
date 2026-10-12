import json
from uuid import UUID

from app.agent.prompts import Passage, wrap_passages
from app.agent.tools.base import (
    AgentTool,
    Confirmation,
    ToolContext,
    ToolOutput,
    parse_args,
)
from app.engineering.assessments import AssessmentIn
from app.engineering.registry import EvidenceRefused
from app.engineering.reports import (
    assessment_for_piece,
    capture_inputs,
    generate_report,
    report_copy,
    save_assessment,
)
from app.engineering.schemas import StrictModel


def permitted(ctx: ToolContext) -> str | None:
    if not ctx.engineering_turn or not ctx.calculators_enabled:
        return "Engineering calculation tool is unavailable; NOT VERIFIED."
    if ctx.package_id is None or ctx.thread_id is None:
        return "An active piece and conversation are required for version-scoped assessment."
    return None


def preview(arguments, ctx):
    if problem := permitted(ctx):
        return problem
    inputs, problem = parse_args(AssessmentIn, arguments)
    if inputs is None:
        return problem
    try:
        with ctx.deps.session() as session:
            snapshot = capture_inputs(
                session, ctx.deps.render_root, ctx.package_id, inputs
            )
        return Confirmation(
            subject="assessment_inputs",
            summary="Confirm these engineering facts/bindings as owner estimates for "
            + ctx.package_id
            + f" v{inputs.version}. This does not verify properties, change geometry or approve installation.\n"
            + json.dumps(inputs.model_dump(mode="json"), ensure_ascii=False),
            proposal={
                **inputs.model_dump(mode="json"),
                "spec_hash": snapshot["geometry"]["spec_hash"],
            },
        )
    except EvidenceRefused as error:
        return str(error)


def record(arguments, ctx):
    if problem := permitted(ctx):
        return problem
    inputs, problem = parse_args(AssessmentIn, arguments)
    if inputs is None:
        return problem
    try:
        with ctx.deps.session() as session:
            assessment = save_assessment(
                session,
                ctx.deps.render_root,
                ctx.package_id,
                inputs,
                owner_id=ctx.owner_id,
                thread_id=ctx.thread_id,
                confirmed=ctx.approved,
            )
            session.commit()
            return ToolOutput(
                text=f"Owner-confirmed assessment input snapshot {assessment.id} for v{inputs.version}. Estimates and capacity remain NOT VERIFIED.",
                update={"engineering_assessment_ids": [str(assessment.id)]},
            )
    except EvidenceRefused as error:
        return str(error)


class CalculateIn(StrictModel):
    assessment_id: UUID


class GetReportIn(StrictModel):
    report_id: UUID


def wrapped_report(packet):
    return wrap_passages(
        [
            Passage(
                content=json.dumps(packet, ensure_ascii=False),
                title="Engineering report " + packet["report_id"],
                url="local immutable assessment",
                scraped_at="recorded snapshot",
            )
        ]
    )


def result(packet):
    return ToolOutput(
        text=wrapped_report(packet),
        update={"engineering_report_ids": [packet["report_id"]]},
    )


def calculate(arguments, ctx):
    if problem := permitted(ctx):
        return problem
    args, problem = parse_args(CalculateIn, arguments)
    if args is None:
        return problem
    try:
        with ctx.deps.session() as session:
            assessment = assessment_for_piece(
                session, args.assessment_id, ctx.package_id
            )
            report = generate_report(session, ctx.deps.render_root, assessment)
            session.commit()
            return result(
                report_copy(
                    session,
                    ctx.deps.render_root,
                    report.id,
                    package_id=ctx.package_id,
                    remote=True,
                )
            )
    except EvidenceRefused as error:
        return str(error)


def get_report(arguments, ctx):
    if problem := permitted(ctx):
        return problem
    args, problem = parse_args(GetReportIn, arguments)
    if args is None:
        return problem
    with ctx.deps.session() as session:
        packet = report_copy(
            session,
            ctx.deps.render_root,
            args.report_id,
            package_id=ctx.package_id,
            remote=True,
        )
    return (
        result(packet)
        if packet
        else "Report is outside the active piece; NOT VERIFIED."
    )


record_assessment_inputs = AgentTool(
    name="record_assessment_inputs",
    description="Propose version-specific loads, exact bindings and installation facts; stores only after explicit owner confirmation, separately from geometry.",
    schema=AssessmentIn,
    preview=preview,
    run=record,
)
calculate_engineering = AgentTool(
    name="calculate_engineering",
    description="Request a version-scoped code-generated engineering report; unavailable/unreviewed methods remain NOT VERIFIED.",
    schema=CalculateIn,
    run=calculate,
)
get_engineering_report = AgentTool(
    name="get_engineering_report",
    description="Fetch a complete current-rights report for the active piece; never reconstruct remembered arithmetic.",
    schema=GetReportIn,
    run=get_report,
)
