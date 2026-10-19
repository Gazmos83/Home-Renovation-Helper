"""homeowner-chat: a "yes" covers only the proposal the owner was shown."""

from __future__ import annotations

from app.agent.foreman import _still_shown
from app.agent.tools.base import Confirmation


def _confirmation(**proposal) -> Confirmation:
    return Confirmation(subject="revision", summary="Change it?", proposal=proposal)


def test_the_proposal_shown_is_still_the_one_that_runs() -> None:
    shown = {"package_id": "hall-bench", "revised_from": 3, "changes": ["width 1200"]}
    assert _still_shown(_confirmation(package_id="hall-bench", revised_from=3, changes=("width 1200",)), {"answer": "yes", "shown": shown})


def test_a_newer_version_or_another_render_target_is_not_what_was_approved() -> None:
    assert not _still_shown(_confirmation(package_id="hall-bench", revised_from=4), {"shown": {"package_id": "hall-bench", "revised_from": 3}})
    assert not _still_shown(_confirmation(target="remote", estimate_seconds=60.0), {"shown": {"target": "local", "estimate_seconds": 60.0}})


def test_an_answer_without_the_shown_proposal_is_not_checked() -> None:
    assert _still_shown(_confirmation(revised_from=4), {"answer": "yes"})
