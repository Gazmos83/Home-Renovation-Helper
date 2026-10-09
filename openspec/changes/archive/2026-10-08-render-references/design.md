## Context

See proposal.md. What exists now:

- `foreman.md` is a router with `tools: []`. Its `reviewer` line asks for "a screenshot or a render" to be "checked against the brief and spec". Feedback that points at a part or a view reads as builder, designer and reviewer work at once. The Foreman runs on `openai/gpt-5.6-luna` and is text-only (`IMAGE_SLOTS = {intake, reviewer}`).
- `revision_review` takes `package_id` and `version` only. The vision request is `REVIEW_NOTE`, then `image {n}: {label}` lines, the spec facts, the brief and the warnings. Items cite `image: int` (1-based, bounded by `review_schema`). `_format_items` prints "(image {n})". `review_items.image` is an integer column exposed by `app/api/reviews.py`.
- `review.collect` labels images as "screenshot", "front view (width and height)", "side view (depth and height)", "top view (width and depth)", "turntable frame {i} of {n}" (0-based), "room still" and "room frame {i} of {n}". It sends at most 10.
- Orientation, checked in code:
  - `build_custom_build._build_cameras_lights` puts `CAM_Front` at −Y, `CAM_Side` at +X and `CAM_Top` above. `CAM_Iso` is along (3.2, −4.5, 2.5), so front and to the +X side.
  - The model is exported with `export_yup=True`, so Blender −Y becomes three.js +Z and +X stays +X.
  - The inspector's `cameraPresets` puts front at +Z, side at +X and top above. So the inspector's Front and Side match `front.png` and `side.png`, and its Iso matches the screenshot's quadrant.
- The turntable (`render_turntable.fill`) starts at `CAM_Iso`'s angle, `atan2(−4.5, 3.2)` ≈ −54.6°. It steps by +2π/frames, counter-clockwise seen from above. It records each frame's `location_mm` and the orbit's `target_mm`, and the runner stores them in the version's `scene.json` under `turntable`.

## Goals / Non-Goals

**Goals:**
- The owner and the Reviewer use the same names for what they look at: the inspector's views.
- The Foreman sends "is this right?" to the Reviewer and "change this" to the Designer, using two short lines.
- The owner's question reaches the vision model safely, as delimited reference text.

**Non-Goals:**
- Clickable or named parts in the inspector (`PieceModel.tsx`: "Part selection was not carried over").
- An exploded image as review evidence. Adding one would be a generator change; it may be a later change.
- Any UI layout. `studio-layout` handles the turntable-viewer links and the split-screen inspector.
- Changing turntable rendering, the render guard, either model, or the stored review shape.

## Decisions

1. **Prompts stay short.**
   - In `foreman.md`, the `reviewer` line becomes: "`reviewer`: the owner asks whether something they see in the inspector (a view such as front or exploded, a module or a part) is right, or wants the piece checked against the brief."
   - Add one rule to `foreman.md`: "A request to change what they see goes to `designer`; a question whether it is right goes to `reviewer`."
   - `reviewer.md` gains three rules: "Name what you looked at by the inspector's views: front, side, top.", "You have no exploded image; for a question about the exploded view, say so and answer from the spec's parts and the views you have." and "Pass the owner's question, in their words, as `focus`."
   - The existing `review_ready` guard on the Reviewer stays as it is.
   - *Alternative:* list view names and direction rules in the Foreman. Rejected because the owner reports that long, code-like rules confuse the Foreman.

2. **View labels are computed in code.**
   - For each spread frame, `collect` reads `scene.json["turntable"]` and takes `cameras[index].location_mm − target_mm`.
   - `angle = atan2(dy, dx)` in Blender axes, and `relative = (angle + 90°) mod 360`, where the front (−Y) is 0°.
   - The name is `DIRECTIONS[round(relative / 45) mod 8]`, with `DIRECTIONS = (front, front-right, right side, back-right, back, back-left, left side, front-left)`. The label is `turntable <name>`.
   - With this mapping, +X is `right side`, which is the inspector's Side camera, and frame 0 of a fresh build (relative ≈ 35°) is `turntable front-right`.
   - A missing or unreadable `scene.json` gives `turntable view k` (k = 1–4 in spread order). If two frames land on the same name, the second gets ` 2` appended.
   - The straight-on views are labelled `front`, `side` and `top`, with the dimensions they show kept as a description line. The screenshot is `iso`. Room images are `room` and `room opposite side`.
   - *Alternative:* derive the angle from the frame index and a fixed start angle. Rejected because the recorded positions are the truth and survive a change to `CAM_Iso`.

3. **Items cite a view name; storage keeps the index.**
   - `review_schema(labels)` builds `BoundItem.view: Literal[*labels]` in place of `image: int`.
   - After validation, the tool maps each `view` back to its 1-based position among `evidence.images` and records `image` as before. The migration, `ReviewItem`, `record_review` and the reviews API do not change.
   - `_format_items` prints "(seen in the {view} view)".
   - The text block lists `{label}: {description}` lines and no numbers. `REVIEW_NOTE` changes "Cite the image number" to "Cite the view name you saw each issue in".

4. **`focus` is untrusted text.**
   - `RevisionReviewArgs.focus: str | None` has `max_length` 500 and the description "what the owner asked to check, in their words".
   - When set, the request text gains `The owner asked:` followed by a delimited block, built the same way as `prompts.wrap_note` (`OPEN_PREFIX source="owner's question"]]]`, `neutralise(focus)`, `CLOSE_TOKEN`).
   - The system message of the nested call becomes `REVIEW_NOTE + UNTRUSTED_CONTENT_PREAMBLE`.
   - The focus steers attention only. It is not recorded on the review and is never quoted as a finding's expectation.

5. **The exploded view has no image.** The Foreman's `reviewer` line names the exploded view, so such a question reaches the Reviewer. The Reviewer's view-naming rule lists only front, side and top. For an exploded-view question it says it has no exploded image and answers from the spec's parts and the views it was sent, naming those views. Decided by the owner (option a).

6. **"Right" is the viewer's right when facing the front.** The direction names are as seen when facing the piece's front, so `right side` is +X, the inspector's Side camera. Confirmed by the owner, 2026-10-08.

## Risks / Trade-offs

- [Left and right are ambiguous] → Settled by decision 6: the viewer's right when facing the front, matching the inspector's Side camera at +X.
- [An exploded-view answer rests on spec parts, not an image] → The Reviewer says so plainly, so the owner knows what it checked.
- [A non-custom-build piece, such as an imported design, may lack `CAM_Front` or the −Y-front convention] → Labels come from recorded camera positions relative to −Y. If such a piece's front is not −Y, the names are wrong. Imported packages follow `build_room_scene`'s "local −Y is the front" note, so this risk is accepted.
- [A Literal of free-text labels grows the structured-output schema] → There are at most 10 short labels, so the cost is negligible.
- [The model may cite a view loosely ("side" for `turntable right side`)] → Validation refuses it and the review reports that it could not be completed, as today for an out-of-range image.
