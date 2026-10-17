"""design-guidelines: `search_guidelines` returns dated passages inside the delimiters."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.agent.prompts import CLOSE_TOKEN, OPEN_PREFIX
from app.guidelines.ingest import ingest_guidelines
from app.guidelines.sources import GuidelineSource
from plugins.guidelines.tool import CITE_NOTE, NOTHING_FOUND, run

pytestmark = pytest.mark.usefixtures("clean_chunks")

GUIDE = "# Transitional style\n\nTransitional rooms pair warm wood tones with clean, simple lines.\n"


@pytest.fixture
def dated_guide(tool_deps, fake_embedder, tmp_path: Path) -> None:
    (tmp_path / "style.md").write_text(GUIDE, encoding="utf-8")
    source = GuidelineSource(
        id="style-guide", title="Style Guide", jurisdiction="-", path="style.md", format="md",
        published_on=date(2020, 1, 1), licence="owner's copy",
    )
    with tool_deps.session() as session:
        report = ingest_guidelines(session, None, [source], root=tmp_path)
        session.commit()
    assert report.ingested.get("style-guide")


def test_a_dated_passage_is_returned_with_its_date(dated_guide, make_ctx) -> None:
    result = run({"query": "transitional style warm wood tones"}, make_ctx())
    assert isinstance(result, str) and result.startswith(CITE_NOTE)
    assert OPEN_PREFIX in result and CLOSE_TOKEN in result
    assert "Style Guide (2020-01-01)" in result


def test_nothing_matched_says_so(make_ctx, fake_embedder) -> None:
    assert run({"query": "transitional style"}, make_ctx()) == NOTHING_FOUND
