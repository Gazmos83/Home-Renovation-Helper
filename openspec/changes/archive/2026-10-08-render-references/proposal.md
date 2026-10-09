## Why

The owner says the Foreman does not reliably send a turntable to the Reviewer, and references are easily misunderstood. What the owner looks at is the Piece Inspector ("Inspect version N") with its Front, Side and Plan cameras and its Exploded mode. The Reviewer instead speaks in frame and image numbers ("turntable frame 3 of 12", "image 5") that the owner never sees. Long, code-like routing rules also confuse the Foreman, so the fix keeps the prompts short and moves the rest into the review tool's code.

## What Changes

- **Foreman prompt** (`foreman.md`): the `reviewer` line becomes "the owner asks whether something they see in the inspector (a view such as front or exploded, a module or a part) is right, or wants the piece checked against the brief". One rule is added: a request to change what they see goes to `designer`; a question whether it is right goes to `reviewer`. Nothing else is added to the Foreman.
- **Reviewer prompt** (`reviewer.md`): one rule to name what it looked at by the inspector's views (front, side, top), one to say it has no exploded image and answer an exploded-view question from the spec's parts and the views it has, and one to pass the owner's question as `focus`.
- **`revision_review` gains `focus`**: an optional string, the owner's question in their own words. It is added to the vision request as "The owner asked: …" inside the untrusted-content delimiters, neutralised, under the untrusted-content preamble.
- **Evidence is labelled by inspector view names**: front, side and top for the straight-on views. Turntable frames are named by the direction their camera looks from (for example "front-right", "right side", "back"), worked out from the frame's camera position, not by frame numbers. Room images keep a room label.
- **The structured answer cites a view name**, chosen from the names that were sent, instead of a 1-based image number. Code maps the name back to the stored image index, so the review record, the migration and the reviews API stay as they are. `_format_items` reads "(seen in the {view} view)". The 10-image cap stays.
- **Non-goals**: clickable or named parts in the inspector; an exploded image as review evidence (that is a generator change, possibly a later change); any UI layout (the parallel `studio-layout` change removes the turntable-viewer links and adds the split-screen inspector); a change to turntable rendering, to the Reviewer's model or to the Foreman's model.

**Ladder step and agent:** no ladder step. This is prompt text and review-tool code; it feeds ladder step 1 as before (a review becomes a revision the owner confirms). Agents: Foreman (prompt only) and Reviewer (prompt and `revision_review`). **Render guard:** not affected; no render is added and the review still never starts one. **bpy allow-list:** not affected; no live Blender.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `render-review`: the evidence is labelled by inspector view names, the owner's question can be passed as a delimited focus, and the discrepancy items cite a view name.
- `design-agents`: the Foreman sends a question about what the owner sees in the inspector to the Reviewer, and a request to change it to the Designer.

## Impact

- Code: `backend/app/agent/instructions/foreman.md`, `backend/app/agent/instructions/reviewer.md`, `backend/plugins/revision_review/tool.py` (`focus`, request text, formatting), `backend/app/agent/review.py` (view labels from frame cameras, schema citing a view).
- Unchanged: `review_items.image` column, `app/api/reviews.py`, `house_file.record_review`'s stored shape, the turntable generator, the render guard.
- Tests: `tests/test_review_evidence.py`, `tests/test_revision_review.py`, `tests/test_instructions.py`, `tests/test_foreman.py`.
- Related: `studio-layout` (parallel; UI only).
