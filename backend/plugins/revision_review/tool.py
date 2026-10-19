"""`revision_review` (Reviewer): a structured discrepancy list, recorded, no other writes."""

from __future__ import annotations

import base64
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, ValidationError

from app.agent import house_file
from app.agent.budget import BudgetRefused, RequestBudget, prepare, refusal_message
from app.agent.models.openrouter_client import gateway_errors
from app.agent.prompts import (
    CLOSE_TOKEN,
    OPEN_PREFIX,
    UNTRUSTED_CONTENT_PREAMBLE,
    neutralise,
)
from app.agent.review import ReviewRefused, collect, review_schema
from app.agent.tools.base import AgentTool, ToolContext, parse_args
from app.agent.tools.shared import version_folder
from app.observability.usage import UsageRecorder, operation, tokens_today

REVIEW_NOTE = (
    "You compare the labelled images with the spec facts and the brief. "
    "List discrepancies. Quote measurements from the spec facts, never from the images. "
    "Cite the view name you saw each issue in. An empty list means no discrepancies."
)


class RevisionReviewArgs(BaseModel):
    package_id: str | None = Field(
        default=None, description="the piece; the conversation's bound piece when left out"
    )
    version: int | None = Field(default=None, description="a version number; the latest when left out")
    focus: str | None = Field(
        default=None,
        max_length=500,
        description="what the owner asked to check, in their words",
    )


def _image_block(path) -> dict[str, Any]:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}}


def _format_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No discrepancies found."
    lines = [f"Review found {len(items)} item(s):"]
    for index, item in enumerate(items, start=1):
        suggestion = f" Suggestion: {item['suggestion']}" if item.get("suggestion") else ""
        lines.append(
            f"{index}. {item['severity']} {item['aspect']}: expected {item['expected']} "
            f"({item['expected_source']}); observed {item['observed']} "
            f"(seen in the {item['view']} view).{suggestion}"
        )
    return "\n".join(lines)


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(RevisionReviewArgs, arguments)
    if args is None:
        return problem
    package_id = args.package_id or ctx.package_id
    if not package_id:
        return "there is no piece bound to this conversation; say which package to review"
    folder, number, problem = version_folder(ctx.deps, package_id, args.version)
    if folder is None or number is None:
        return problem
    try:
        evidence = collect(ctx.deps.render_root, package_id, number)
    except ReviewRefused as error:
        return str(error)

    brief = dict(ctx.brief)
    with ctx.deps.session() as session:
        pieces = {p["package_id"]: p for p in house_file.pieces(session, ctx.deps.render_root)}
    stored = pieces.get(package_id) or {}
    if stored.get("brief"):
        brief = dict(stored["brief"])

    labels = "\n".join(
        f"{image.label}: {image.description}" if image.description else image.label
        for image in evidence.images
    )
    brief_text = json_brief(brief)
    warnings = "\n".join(evidence.warnings) if evidence.warnings else "(none)"
    text = (
        f"{REVIEW_NOTE}\n\nImages:\n{labels}\n\nSpec facts:\n{evidence.facts or '(none)'}\n\n"
        f"Brief:\n{brief_text}\n\nDesign-rule warnings:\n{warnings}"
    )
    if args.focus:
        text += (
            f'\n\nThe owner asked:\n{OPEN_PREFIX} source="owner\'s question"]]]\n'
            f"{neutralise(args.focus)}\n{CLOSE_TOKEN}"
        )
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for image in evidence.images:
        content.append(_image_block(image.path))
    schema = review_schema([image.label for image in evidence.images])
    slug = ctx.deps.model_id("reviewer")
    try:
        provide = ctx.deps.model_provider
        model = provide("reviewer")
        # Counted and checked against the day's ceiling like every other call (token-budget).
        restrictions = ctx.deps.budgets.for_model(slug)
        cap = getattr(model, "max_tokens", None)
        request_budget = RequestBudget.for_model(
            slug,
            context_budget_tokens=restrictions.context_budget_tokens,
            max_output_tokens=cap if isinstance(cap, int) else None,
        )
        prompt, counted = prepare(
            request_budget,
            f"{REVIEW_NOTE}\n\n{UNTRUSTED_CONTENT_PREAMBLE}",
            [HumanMessage(content=content)],
            used_today=tokens_today(ctx.deps.engine, slug, ctx.deps.settings.budget_timezone),
            daily_ceiling=restrictions.daily_token_ceiling,
        )
    except BudgetRefused as error:
        return refusal_message("reviewer", error)
    try:
        with gateway_errors(operation="chat.reviewer.review"), operation("chat.reviewer.review"):
            result = model.with_structured_output(schema).invoke(
                prompt,
                config={
                    "callbacks": [
                        UsageRecorder(
                            ctx.deps.engine,
                            model_id=slug,
                            owner_user_id=ctx.owner_id,
                            estimated_tokens=counted,
                        )
                    ]
                },
            )
    except ValidationError:
        return "the review could not be completed"
    except Exception:  # noqa: BLE001 - a failed nested call must not end the turn
        return "the review could not be completed"

    payload = result.model_dump()
    items = payload.get("items") or []
    positions = {image.label: index for index, image in enumerate(evidence.images, start=1)}
    recorded = [{**item, "image": positions[item["view"]]} for item in items]
    with ctx.deps.session() as session:
        house_file.record_review(session, package_id, number, evidence.renders, recorded)
        session.commit()
    return _format_items(items)


def json_brief(brief: dict[str, Any]) -> str:
    if not brief:
        return "(none)"
    parts = [f"{key}: {value}" for key, value in brief.items() if value is not None]
    return "; ".join(parts) if parts else "(none)"


revision_review = AgentTool(
    name="revision_review",
    description=(
        "Compare a built version's screenshot and renders with its spec and the brief. "
        "Returns a discrepancy list. Does not build, render or change the piece."
    ),
    schema=RevisionReviewArgs,
    run=run,
)
