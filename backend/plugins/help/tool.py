"""`read_help` (Intake): the Studio's help topics (help-center).

Read-only. With no topic it lists every topic's id and title; with a topic id it
returns that topic as the Help page shows it, inside the untrusted-content
delimiters. Nothing is written.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent.prompts import Passage, wrap_passages
from app.agent.tools.base import AgentTool, ToolContext, parse_args
from app.help import load_help, topic_text

HELP = load_help()


class ReadHelpArgs(BaseModel):
    topic: str | None = Field(
        default=None,
        description=f"optional topic id, one of: {', '.join(HELP.ids())}; omit to list the topics",
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(ReadHelpArgs, arguments)
    if args is None:
        return problem
    if args.topic is None:
        return "Help topics:\n" + "\n".join(f"- {topic.id}: {topic.title}" for topic in HELP.topics)
    found = HELP.topic(args.topic)
    if found is None:
        return f"there is no help topic {args.topic!r}; the topics are {', '.join(HELP.ids())}"
    return wrap_passages(
        [Passage(content=topic_text(found), title=found.title, url=f"help:{found.id}", scraped_at="shipped help")]
    )


read_help = AgentTool(
    name="read_help",
    description=(
        "Read the Studio's help to answer a question about how to use the app. "
        "Call it with no topic to list the topics, then with a topic id to read one. Read-only."
    ),
    schema=ReadHelpArgs,
    run=run,
)
