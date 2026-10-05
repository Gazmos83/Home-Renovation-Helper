"""A scripted chat model, so the agent suite runs with no key and no network.

Controlling the model is what makes the interesting scenarios testable: a tool
call with a field the schema does not define, a gateway that times out, a
Foreman that routes to the Builder too early. What this does not prove is that a
real model follows the instruction files; the `--live` suite is where that is
checked.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from pydantic import BaseModel, ConfigDict, Field


def tool_call(name: str, args: dict[str, Any], call_id: str | None = None) -> dict[str, Any]:
    return {"name": name, "args": args, "id": call_id or f"call-{name}", "type": "tool_call"}


class FakeChatModel(BaseChatModel):
    """Returns scripted answers and records every prompt it was given."""

    replies: list[str] = Field(default_factory=list)
    # One list of tool-call dicts per `.invoke()`, popped in order; a call after
    # every script is used falls back to `replies`.
    tool_call_scripts: list[list[dict[str, Any]]] = Field(default_factory=list)
    # An ordered script mixing both: a string is a text reply, a list is a set of
    # tool calls. Used when a test needs calls and replies interleaved across turns.
    steps: list[str | list[dict[str, Any]]] = Field(default_factory=list)
    # The Foreman's decisions, as `{"specialist": ..., "reason": ...}` dicts or
    # schema instances, popped by `with_structured_output`.
    decisions: list[Any] = Field(default_factory=list)
    # What `bind_tools()` was last called with, by name.
    bound_tools: list[str] = Field(default_factory=list)
    prompts: list[list[BaseMessage]] = Field(default_factory=list)
    decision_prompts: list[list[BaseMessage]] = Field(default_factory=list)
    error: Exception | None = None
    calls: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.prompts.append(list(messages))
        self.calls += 1
        if self.error is not None:
            raise self.error
        # A nominal, non-zero usage on every message so a usage-recording test
        # has something to assert on.
        usage_metadata = {"input_tokens": 5, "output_tokens": 5, "total_tokens": 10}
        if self.steps:
            step = self.steps.pop(0)
            if isinstance(step, str):
                return ChatResult(
                    generations=[
                        ChatGeneration(message=AIMessage(step, usage_metadata=usage_metadata))  # type: ignore[arg-type]
                    ]
                )
            message = AIMessage(
                content="", tool_calls=step, usage_metadata=usage_metadata  # type: ignore[arg-type]
            )
            return ChatResult(generations=[ChatGeneration(message=message)])
        # A scripted tool call only fires while tools are bound: `bind_tools([])`
        # (the round cap) must answer in text even with a script still queued.
        if self.tool_call_scripts and self.bound_tools:
            calls = self.tool_call_scripts.pop(0)
            message = AIMessage(
                content="", tool_calls=calls, usage_metadata=usage_metadata  # type: ignore[arg-type]
            )
            return ChatResult(generations=[ChatGeneration(message=message)])
        text = self.replies.pop(0) if self.replies else "Done."
        return ChatResult(
            generations=[
                ChatGeneration(message=AIMessage(text, usage_metadata=usage_metadata))  # type: ignore[arg-type]
            ]
        )

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> FakeChatModel:
        self.bound_tools = [
            getattr(tool, "name", None) or getattr(tool, "__name__", None) or str(tool)
            for tool in tools
        ]
        return self

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Runnable[Any, Any]:
        def decide(messages: Any, config: RunnableConfig | None = None) -> Any:
            self.decision_prompts.append(list(_as_messages(messages)))
            value = (
                self.decisions.pop(0)
                if self.decisions
                else {"specialist": "intake", "reason": "default"}
            )
            payload = value.model_dump_json() if isinstance(value, BaseModel) else json.dumps(value)
            # Through `invoke`, so callbacks (usage, tracing) fire as for a real model.
            self.steps.insert(0, payload)
            message = self.invoke(messages, config=config)
            return schema.model_validate_json(str(message.content))

        return RunnableLambda(decide)

    def last_prompt_text(self) -> str:
        if not self.prompts:
            return ""
        return "\n".join(str(message.content) for message in self.prompts[-1])


def _as_messages(value: Any) -> Sequence[BaseMessage]:
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [item for item in value if isinstance(item, BaseMessage)]
    return []
