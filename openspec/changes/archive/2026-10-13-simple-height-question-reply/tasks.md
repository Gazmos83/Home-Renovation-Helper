## 1. The rule

- [x] 1.1 Add a matcher for the short expected-height question and the fixed reply constant, in `app/engineering/chat.py` or `foreman.py`. Verify with unit tests: "What's expected height", "what is the maximum height?" and "Expected height?" match; a longer question, a safety or load question, a kitchen part and "expected depth" do not.
- [x] 1.2 Apply it in the Foreman after the routing decision and before the engineering branch, ending the turn with the fixed text and no specialist call. Verify with a graph test that the reply is exactly the fixed text, the specialist models are not called, and a normal engineering question still reaches the engineering path.

## 2. Checks

- [x] 2.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` (one process, a private test database) and record the results here. Result 2026-10-13, on an export of exactly the committed files, run alone on a private database: ruff clean; pytest -m "not slow" 2459 passed, 39 skipped, 1 failed. The failure (`test_the_servers_own_render_time_is_preferred_when_it_reports_one`) was a missing file in the shared pytest temp folder while another session ran pytest; it passes alone. The unrelated kitchen seed test was deselected (it fails without these changes too).
- [x] 2.2 Owner check: ask "What's expected height" in a conversation and see the two-sentence reply. Owner check 2026-10-13: the owner asked "What's expected height" and the reply was correct.
