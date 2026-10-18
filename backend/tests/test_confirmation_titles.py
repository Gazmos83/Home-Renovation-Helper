"""confirmation-summaries: every confirmation has a plain title, and its table reaches the history."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain_core.messages import HumanMessage, ToolMessage

from app.agent import chat

PLUGINS = Path(__file__).resolve().parents[1] / "plugins"


def test_every_confirmation_subject_in_the_plugins_has_a_title() -> None:
    subjects = {
        found
        for path in PLUGINS.rglob("*.py")
        for found in re.findall(r'Confirmation\(\s*subject="([a-z_]+)"', path.read_text())
    }
    assert "compose_room" in subjects and "revise" in subjects
    assert sorted(s for s in subjects if s not in chat.CONFIRMATION_TITLES) == []
    for subject in subjects:
        assert "_" not in chat.confirmation_title(subject)


def test_an_unknown_subject_is_titled_confirmation() -> None:
    assert chat.confirmation_title("frobnicate") == "Confirmation"


class _Graph:
    """A checkpoint stand-in holding one thread's messages."""

    def __init__(self, messages: list[Any]) -> None:
        self.values = {"messages": messages}

    def get_state(self, config: Any, subgraphs: bool = False) -> Any:
        return SimpleNamespace(values=self.values, interrupts=(), tasks=())


def _answered(answered: dict[str, Any]) -> list[dict[str, Any]]:
    tool = ToolMessage("done", tool_call_id="c1")
    tool.additional_kwargs["confirmation"] = answered
    graph = _Graph([HumanMessage("compose Wohnen"), tool])
    from uuid import uuid4

    return chat.history(graph, thread_id=uuid4(), owner_id=uuid4())


TABLE = {
    "columns": ["Item", "Kind", "Size (mm)", "Placement", "Centre (mm)", "Rotation"],
    "rows": [
        ["Sofa", "stand-in", "2000 × 900 × 800", "wall 2, 400 mm", "1400, 450", "0°"],
        ["Lamp", "model", "400 × 400 × 1600", "free, 0°", "1800, 2100", "0°"],
    ],
}


def test_a_room_change_keeps_its_calculations() -> None:
    entry = _answered({"subject": "compose_room", "summary": "Room Wohnen: 2 item(s)", "answer": "yes", "reason": None, "table": TABLE})[-1]
    assert entry["title"] == "Composing room"
    assert entry["answer"] == "yes" and "reason" not in entry
    assert entry["table"] == TABLE
    assert "compose_room" not in entry["title"] + entry["summary"]


def test_a_confirmation_answered_before_titles_existed_has_a_title_and_no_table() -> None:
    entry = _answered({"subject": "compose_room", "summary": "Room Wohnen: the room only", "answer": "no", "reason": "later"})[-1]
    assert entry["title"] == "Composing room"
    assert entry["summary"] == "Room Wohnen: the room only"
    assert entry["reason"] == "later" and "table" not in entry
