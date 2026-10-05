"""`revision_review` (Reviewer). Filled in by render-reviewer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent.tools.base import AgentTool, ToolContext, parse_args

UNAVAILABLE = (
    "revision_review is not available yet. "
    "Tell the owner a review cannot be run yet."
)


class RevisionReviewArgs(BaseModel):
    package_id: str
    version: int | None = Field(default=None, description="a version number; the latest when left out")


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(RevisionReviewArgs, arguments)
    if args is None:
        return problem
    return UNAVAILABLE


revision_review = AgentTool(
    name="revision_review",
    description="Compare a render and its spec against the brief and list discrepancies. Writes nothing.",
    schema=RevisionReviewArgs,
    run=run,
)
