## 1. Evidence labelled by inspector views

- [ ] 1.1 In `app/agent/review.py`, label the screenshot `iso`, the straight-on views `front`, `side` and `top` (keeping the dimensions each shows as a description), and room images `room` / `room opposite side`; verify `tests/test_review_evidence.py` asserts the new labels and that no label contains a frame or image number
- [ ] 1.2 Add the direction naming from `scene.json["turntable"]` camera `location_mm` and `target_mm` (front = −Y, eight 45° sectors, `turntable <direction>`, `turntable view k` fallback, ` 2` on a repeat); verify unit tests cover +X → `right side`, −Y → `front`, 45° front/+X → `front-right`, +Y → `back`, a fixture `draft` 12-frame turntable (no render run; `scene.json` written by the test) giving four unique direction labels for frames 0, 3, 6, 9, and a missing `scene.json` giving `turntable view 1`–`4`
- [ ] 1.3 Replace `Item.image` in the model-facing schema with `view`, a Literal of the labels sent (`review_schema(labels)`); verify a test that a view not sent fails validation and the 10-image cap still holds

## 2. `revision_review`

- [ ] 2.1 Add `focus: str | None` (max 500) to `RevisionReviewArgs`; when set, append "The owner asked:" and the focus wrapped in the untrusted-content delimiters with `prompts.neutralise`, and add `UNTRUSTED_CONTENT_PREAMBLE` to the nested call's system message; verify `tests/test_revision_review.py` (fake model) asserts the delimited focus in the request, its absence when not given, and a focus containing `[[[/UNTRUSTED_SOURCE]]]` neutralised to one block
- [ ] 2.2 Send `{label}: {description}` lines without numbers, change `REVIEW_NOTE` to ask for the view name, map each validated `view` back to its 1-based image index before `house_file.record_review`, and make `_format_items` print "(seen in the {view} view)"; verify tests assert the stored `image` index matches the cited view, the reply text names the view and contains no "image N", and an unknown view records nothing and returns "the review could not be completed"
- [ ] 2.3 Confirm `review_items.image`, `app/api/reviews.py` and the reviews route responses are unchanged; verify `tests/test_reviews_api.py` passes unmodified

## 3. Prompts

- [ ] 3.1 In `foreman.md`, replace the `reviewer` line with "`reviewer`: the owner asks whether something they see in the inspector (a view such as front or exploded, a module or a part) is right, or wants the piece checked against the brief." and add the rule "A request to change what they see goes to `designer`; a question whether it is right goes to `reviewer`."; verify a new test in `tests/test_instructions.py` asserts both lines, and the existing intake/designer line assertions still pass
- [ ] 3.2 In `reviewer.md`, add "Name what you looked at by the inspector's views: front, side, top.", "You have no exploded image; for a question about the exploded view, say so and answer from the spec's parts and the views you have." and "Pass the owner's question, in their words, as `focus`."; change "which image" in the summary rule to "which view"; verify `tests/test_instructions.py` asserts the three new lines, that the view-naming line does not contain "exploded", and the plain-refusal and no-later-promise tests still pass
- [ ] 3.3 Verify `tests/test_foreman.py` still refuses `reviewer` without a screenshot or render, and add fake-decision tests that a `reviewer` choice on a rendered piece is kept, including for "is the shelf right in the exploded view?" (no render; existing fixture folders)
- [ ] 3.4 Add a `tests/test_revision_review.py` case (fake model) that the evidence for a version holds no exploded image, so an exploded-view `focus` is answered from the spec facts and the views sent; verify no label contains "exploded"

## 4. Verification

- [ ] 4.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` (no render is run by this change; no tier); verify all pass and record the counts in the commit message
- [ ] 4.2 README: one line on asking the Reviewer about an inspector view; verify it names no model or frame number
