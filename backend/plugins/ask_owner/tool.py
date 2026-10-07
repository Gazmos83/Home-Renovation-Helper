"""`ask_owner` (Intake, the Designer): questions the owner answers in a form (design-agents).

The preview validates the questions by code and pauses the turn on them; an
invalid set is refused to the model and pauses nothing. The owner's answers, or
their own words when they decline the form, come back as this tool's result in
the same turn (studio-chat-polish design decision 2).
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent.prompts import neutralise
from app.agent.tools.base import AgentTool, Questions, ToolContext, parse_args


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=200, description="the question, one figure or choice")
    unit: str | None = Field(default=None, max_length=20, description="the answer's unit, such as mm or EUR")
    choices: list[Annotated[str, Field(min_length=1, max_length=60)]] | None = Field(
        default=None,
        min_length=2,
        max_length=8,
        description="two to eight answers to offer as buttons; the owner may still answer freely",
    )


class AskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[Question] = Field(min_length=1, max_length=8, description="one to eight questions, in order")


def _valid(args: dict[str, Any]) -> AskArgs | str:
    parsed, refusal = parse_args(AskArgs, args)
    return parsed if isinstance(parsed, AskArgs) else refusal


def preview(args: dict[str, Any], ctx: ToolContext) -> Questions | str:
    parsed = _valid(args)
    if isinstance(parsed, str):
        return parsed
    return Questions(
        questions=[
            {"text": q.text.strip(), "unit": (q.unit or "").strip() or None, "choices": list(q.choices or [])}
            for q in parsed.questions
        ]
    )


def run(args: dict[str, Any], ctx: ToolContext) -> str:
    parsed = _valid(args)
    if isinstance(parsed, str):
        return parsed
    answer = ctx.answer or {}
    declined = answer.get("declined")
    if isinstance(declined, str) and declined.strip():
        return (
            "The owner did not answer the questions and wrote instead: "
            f'"{neutralise(declined.strip())}". Continue from what they wrote.'
        )
    answers = list(answer.get("answers") or [])
    lines = ["The owner answered:"]
    for number, (question, given) in enumerate(zip(parsed.questions, answers, strict=False), start=1):
        unit = f" {question.unit}" if question.unit else ""
        lines.append(f"{number}. {neutralise(question.text)} → {neutralise(str(given))}{unit}")
    return "\n".join(lines)


ask_owner = AgentTool(
    name="ask_owner",
    description=(
        "Ask the owner two or more questions as a form they answer one at a time, each with an "
        "optional unit (mm, EUR) and optional choices. Use it when several figures or choices "
        "are missing. The answers come back as this tool's result in the same turn."
    ),
    schema=AskArgs,
    run=run,
    preview=preview,
)
