"""render-review: revision_review structured call, recording, validation."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.house_file import record_piece, record_version
from app.db.models import Review, ReviewItem
from plugins.revision_review.tool import run
from tests.fakes import FakeChatModel
from tests.test_review_evidence import _png, _version

ITEM = {
    "aspect": "brief",
    "expected": "two drawers",
    "expected_source": "brief",
    "observed": "one drawer",
    "image": 1,
    "severity": "major",
}


def _ready(tool_state: SimpleNamespace, *, frames: int = 0) -> None:
    root = tool_state.settings.render_root
    folder = _version(root, "hall-bench", 1)
    _png(folder / "screenshot.png")
    for index in range(frames):
        _png(folder / "frames" / f"frame_{index:03d}.png")
    with Session(tool_state.engine) as session:
        record_piece(session, "hall-bench", "Hall bench", brief={"purpose": "two drawers"})
        record_version(session, "hall-bench", 1)
        session.commit()


def _ctx(make_ctx, tool_state, model: FakeChatModel):
    tool_state.models = {"reviewer": model}
    return make_ctx(package_id="hall-bench")


def test_image_blocks_reach_the_reviewer_model(tool_state, make_ctx) -> None:
    _ready(tool_state, frames=12)
    model = FakeChatModel(decisions=[{"items": [ITEM]}])
    ctx = _ctx(make_ctx, tool_state, model)

    text = run({}, ctx)

    assert "major brief" in text
    human = model.decision_prompts[-1][-1]
    blocks = human.content
    assert isinstance(blocks, list)
    images = [block for block in blocks if block.get("type") == "image_url"]
    assert len(images) == 5  # screenshot + four frames
    assert "image 1: screenshot" in str(blocks[0])
    assert "turntable frame 0 of 12" in str(blocks[0])


def test_a_valid_list_is_recorded(tool_state, make_ctx) -> None:
    _ready(tool_state)
    model = FakeChatModel(decisions=[{"items": [ITEM]}])
    run({}, _ctx(make_ctx, tool_state, model))
    with Session(tool_state.engine) as session:
        review = session.scalars(select(Review)).one()
        items = session.scalars(select(ReviewItem)).all()
    assert review.package_id == "hall-bench"
    assert review.version == 1
    assert "screenshot.png" in review.renders
    assert len(items) == 1
    assert items[0].aspect == "brief"
    assert items[0].status == "open"


def test_an_empty_list_is_recorded_as_no_discrepancies(tool_state, make_ctx) -> None:
    _ready(tool_state)
    model = FakeChatModel(decisions=[{"items": []}])
    text = run({}, _ctx(make_ctx, tool_state, model))
    assert "No discrepancies" in text
    with Session(tool_state.engine) as session:
        assert session.scalars(select(Review)).one() is not None
        assert session.scalars(select(ReviewItem)).all() == []


def test_an_invalid_answer_records_nothing(tool_state, make_ctx) -> None:
    _ready(tool_state)
    model = FakeChatModel(decisions=[{"nope": True}])
    text = run({}, _ctx(make_ctx, tool_state, model))
    assert "could not be completed" in text
    with Session(tool_state.engine) as session:
        assert session.scalars(select(Review)).all() == []


def test_an_image_index_out_of_range_is_refused(tool_state, make_ctx) -> None:
    _ready(tool_state)
    bad = {**ITEM, "image": 9}
    model = FakeChatModel(decisions=[{"items": [bad]}])
    text = run({}, _ctx(make_ctx, tool_state, model))
    assert "could not be completed" in text
    with Session(tool_state.engine) as session:
        assert session.scalars(select(Review)).all() == []
