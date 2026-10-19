"""`search_guidelines` (Designer, Researcher): look up an official rule or an owner's note.

Passages reach the model only inside the untrusted-content delimiters, with the
publication or note, its section and its date; nothing matched is said plainly.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Final

from pydantic import BaseModel, Field

from app.agent.prompts import Passage, wrap_passages
from app.agent.tools.base import AgentTool, ToolContext, ToolOutput, parse_args
from app.retrieval import search_knowledge

logger = logging.getLogger("app")

NOTHING_FOUND: Final = (
    "No guideline passage matched. Say that you found no guideline for this rather than "
    "stating a rule from memory."
)
LOOKUP_FAILED: Final = "The guideline store could not be consulted. Tell the owner the lookup was unavailable."
CITE_NOTE: Final = (
    "These are guideline passages. When you quote one, name its source (the publication or "
    "the owner's note) and its section."
)


class SearchGuidelinesArgs(BaseModel):
    query: str = Field(min_length=1, max_length=400, description="the rule, room or piece to look up")


def run(arguments: dict[str, Any], ctx: ToolContext) -> str | ToolOutput:
    args, problem = parse_args(SearchGuidelinesArgs, arguments)
    if args is None:
        return problem
    if ctx.engineering_turn:
        # The engineering adapter applies the same rights and remote-use gates.
        from app.agent.tools import loaded_plugins

        tool = loaded_plugins().builtin_tools()["search_engineering_knowledge"]
        return tool.run({"query": args.query}, ctx)
    try:
        with ctx.deps.session() as session:
            hits = search_knowledge(session, args.query.strip(), limit=5, categories=["guideline"])
    except Exception as error:  # noqa: BLE001 - a lookup failure is a stated inability
        logger.warning("guideline search failed", extra={"context": {"error_type": type(error).__name__}})
        return LOOKUP_FAILED
    return search_result(hits)


def search_result(hits: list[Any]) -> str:
    """What the model is given for these hits (also read by the offline eval)."""
    if not hits:
        return NOTHING_FOUND
    passages = []
    for hit in hits:
        passage = Passage.from_hit(hit)
        if hit.published_on is not None:
            passage = replace(passage, title=f"{passage.title} ({hit.published_on.isoformat()})".strip())
        passages.append(passage)
    return CITE_NOTE + "\n\n" + wrap_passages(passages)


search_guidelines = AgentTool(
    name="search_guidelines",
    description="Search design guidelines and the owner's notes for a placement or piece rule; cite the source.",
    schema=SearchGuidelinesArgs,
    run=run,
)
