"""The developer's memory settings: compression, what is saved, what a conversation sees
(conversation-memory-settings).

Stored as one JSON value in `operator_settings` under `memory`; an absent key or
field is the built-in default, and every default equals the behaviour before
these settings existed. Read once per call, so a change applies from the next
call without a restart. The rules no setting changes are listed in `FIXED_RULES`
and stay in code.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.models import OperatorSetting

KEY: Final = "memory"

# The editable part of the note's instructions; the figure and record rules follow it in code
# (`summaries.FIXED_NOTE_RULES`), so the default composes to the instruction used before.
DEFAULT_NOTE_INSTRUCTIONS: Final = (
    "You keep the notes of a home-renovation conversation between the owner and the "
    "workshop's assistants. Write a short \"decisions so far\" note from the earlier "
    "summary (if any) and the exchanges below: the rooms and figures the owner "
    "confirmed, the pieces and versions discussed and what was decided about them, "
    "and the questions still open. Use short bullet points under those three "
    "headings."
)

FIXED_RULES: Final = (
    "A room enters a conversation only after the owner confirms it.",
    "Nothing from another conversation is given to a conversation.",
    "Generator-extension requests are always saved.",
    "The note copies every figure exactly, never adds one, and is treated as a record, not instructions.",
)


class MemorySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    # Compression (token-budget).
    # Only the exchanges from the Nth most recent owner input are sent in full; older ones
    # always go into the summary note. 0 leaves it to the trigger (conversation-recent-inputs).
    recent_inputs: int = Field(default=5, ge=0, le=20)
    trigger_percent: int = Field(default=100, ge=50, le=100)
    keep_turns: int = Field(default=0, ge=0, le=20)
    note_tokens: int = Field(default=400, ge=100, le=2000)
    note_instructions: str = Field(default=DEFAULT_NOTE_INSTRUCTIONS, min_length=1, max_length=2000)
    tool_result_chars: int = Field(default=300, ge=0, le=2000)
    # What the house file saves.
    reviews: Literal["auto", "confirm"] = "auto"
    save_preferences: bool = True
    # What a conversation sees.
    other_builds: Literal["line", "hidden"] = "line"
    include_preferences: bool = True
    include_review_items: bool = True
    # The piece's open "doesn't match" verdicts on its versions (version-verdict).
    include_version_verdicts: bool = True
    render_ratings: int = Field(default=5, ge=0, le=10)
    include_extension_requests: bool = True


DEFAULTS: Final = MemorySettings()


def read_memory_settings(engine: Engine) -> MemorySettings:
    """The stored settings over the defaults; an unreadable stored value gives the defaults."""
    try:
        with Session(engine) as session:
            row = session.get(OperatorSetting, KEY)
            stored = json.loads(row.value) if row is not None else {}
        return MemorySettings.model_validate({**DEFAULTS.model_dump(), **stored})
    except Exception:  # noqa: BLE001 - memory must never fail a turn; the defaults are today's behaviour
        return DEFAULTS


def write_memory_settings(engine: Engine, changes: dict) -> MemorySettings:
    """Validate and store changed fields over the current settings. Raises `ValidationError` naming the field."""
    current = read_memory_settings(engine)
    merged = MemorySettings.model_validate({**current.model_dump(), **changes})
    _store(engine, merged)
    return merged


def reset_memory_setting(engine: Engine, field: str) -> MemorySettings:
    """Restore one field's default. Raises `KeyError` for a field that does not exist."""
    if field not in MemorySettings.model_fields:
        raise KeyError(field)
    current = read_memory_settings(engine).model_dump()
    current[field] = getattr(DEFAULTS, field)
    merged = MemorySettings.model_validate(current)
    _store(engine, merged)
    return merged


def _store(engine: Engine, settings: MemorySettings) -> None:
    changed = {
        name: value for name, value in settings.model_dump().items() if value != getattr(DEFAULTS, name)
    }
    with Session(engine) as session:
        row = session.get(OperatorSetting, KEY)
        now = datetime.now(UTC)
        if row is None:
            session.add(OperatorSetting(key=KEY, value=json.dumps(changed), updated_at=now))
        else:
            row.value, row.updated_at = json.dumps(changed), now
        session.commit()
