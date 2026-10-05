"""`search_guidelines` (Designer): look up a design rule. Filled in by pricing-researcher."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent.tools.base import AgentTool, ToolContext, parse_args

UNAVAILABLE = (
    "search_guidelines is not available yet: guideline sources have not been loaded. "
    "Tell the owner this lookup cannot be done yet."
)


class SearchGuidelinesArgs(BaseModel):
    query: str = Field(description="the rule, room or piece to look up")


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(SearchGuidelinesArgs, arguments)
    if args is None:
        return problem
    return UNAVAILABLE


search_guidelines = AgentTool(
    name="search_guidelines",
    description="Search design guidelines and the owner's notes for a placement or piece rule.",
    schema=SearchGuidelinesArgs,
    run=run,
)
