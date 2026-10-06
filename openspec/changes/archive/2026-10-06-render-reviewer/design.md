## Context

See proposal.md. What exists after `apartment-intake` and `pricing-researcher`: the Foreman graph with five specialists, image content blocks expanded in the agent node for image slots (`apartment-intake` decision 3), `IMAGE_SLOTS = {intake, reviewer}`, the `reviewer` slot routed to `deepseek/deepseek-v4.1-flash`, version folders with `screenshot.png` (800×500), `still.png`, `frames/frame_NNN.png` and `room/…` at tier resolutions, `spec.json`/`input.json`, the piece brief in `pieces.brief`, and design-rule checks (`app/guidelines/checks.py`). The predecessor had no reviewer of renders and never sent an image to a model; its material review was deterministic rules — nothing to port beyond the structured-output and no-write patterns.

## Goals / Non-Goals

**Goals:**
- After a draft turntable, "check it" yields a short, validated list of discrepancies against the brief and spec, recorded, and actionable by the Designer through a confirmed revision.
- The Reviewer can see but never change anything.

**Non-Goals:**
- Automatic reviews after every render; reviewing shells; pixel-accurate measurement from images; feedback learning from reviews (step 9).
- A Studio page for reviews (the chat and Studio viewer change shows them).

## Decisions

1. **Evidence chosen by code, not the model.** `review.collect(root, package_id, version)`: `screenshot.png` if present; turntable frames at indices `round(k·n/4)` for k = 0..3 (n = frame count) or `still.png`; `room/still.png` or two room frames 180° apart; max six images, each sent at its stored size (tier-bounded: 600–1500 px). Text facts from `spec.json` (else derived from `input.json`): overall, per-module size, shelves, fronts by type and count, material slots, cut-list rows and hardware lines; the brief; design-rule warnings recomputed for the version. Each image is labelled (`image 1: screenshot`, `image 2: turntable frame 3 of 12`, …) so items can cite it.

2. **One structured call.** The Reviewer specialist's agent node is the normal loop; `revision_review` is a tool whose `run` performs the evidence assembly and a nested structured-output call on the Reviewer slot's model (`with_structured_output(Review)`, the same pattern as the Foreman's `Decision`), inside `gateway_errors(operation="chat.reviewer.review")` with the slot's usage recorder. The tool returns the validated items as text for the Reviewer to summarise to the owner. *Alternative:* images inline in the Reviewer's own agent prompt and a free-text answer; rejected because a free-text list cannot be validated or recorded.

3. **Schema.** `Review{items: list[Item] (≤ 20)}`, `Item{aspect: Literal[...], expected: str, expected_source: Literal["brief","spec","rule"], rule_id?: str, observed: str, image: int (1-based, ≤ number sent), severity: Literal["minor","major"], suggestion?: str}`; strings bounded. A validation failure → the tool returns "the review could not be completed" and records nothing. The prompt (`reviewer.md` + a fixed note) forbids estimating measurements from images and asks to quote the spec's number.

4. **Records.** Table `reviews` (id, package_id, version, renders JSONB — which files were used, created_at) and `review_items` (id, review_id, ordinal, aspect, expected, expected_source, rule_id, observed, image, severity, suggestion, status `open|resolved|dismissed`, status_at). The model id is not stored on the review (the usage row holds it, out of the homeowner's sight). `house_note` for the Designer gains "Open review items" from the latest review of the bound piece.

5. **Routing rule.** `load_house` computes `review_ready` (latest version of the bound piece has `screenshot.png` or a render); the Foreman never chooses `reviewer` without it, falling back to the Builder (if a version exists) or Intake/Designer by the existing rules. `reviewer.md` header: `slot: reviewer`, `tools: [revision_review]`.

6. **Routes.** `GET /packages/{id}/versions/{n}/reviews` (items with status), `PATCH /reviews/{review_id}/items/{item_id} {status: resolved|dismissed}` (owner-gated). No route starts a review: it is a conversation action.

## Risks / Trade-offs

- [The vision model hallucinates a discrepancy] → Items must cite an image and a source; the owner closes items; nothing changes without a confirmed revision.
- [Image tokens cost] → At most six images per review, only on request; step 7's budget counts them.
- [Same-family drift if routing changes] → Routing validation already refuses a text-only Reviewer; a family check is not added (owner's routing choice).

## Migration Plan

Migration `0005_reviews` adds `reviews` and `review_items`. Rollback drops them; no other data depends on them.

## Open Questions

None.
