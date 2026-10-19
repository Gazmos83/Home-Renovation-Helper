## Context

See proposal.md (Why). Current state:
- `BriefIn.max_piece_height_mm` is already `float | None` (`backend/app/api/chat.py:567`) and `BriefPanel.tsx` already sends `null` for an empty field (`number()` returns `null`; `undefined` means invalid). The field is "required" only in Intake's instruction ("the purpose, the heights, the style and the budget", `intake.md:16`) and the design-agents "Missing height" scenario.
- `record_brief` (`backend/plugins/intake/tool.py:54`) takes `max_piece_height_mm: float | None`.
- A piece's room is `Piece.room_id` → `Room.corners_mm`, `Room.height_mm`. A version's size is `overall(document)` (`w`, `d`, `h`), already read in `packages.py:343` on approval and in `room_contract` for placement.
- `notices.build_text` / `post_build` compose the build notice (`backend/app/agent/notices.py:118-146`).
- `describe_version` (`backend/app/api/packages.py`) feeds the inspector.

## Goals / Non-Goals

**Goals:**
- The owner is not asked for a limit they do not care about.
- A version that cannot stand in its room is flagged where the owner looks: the build notice and the inspector.

**Non-Goals:**
- Refusing a build or an approval for size.
- Checking depth, door swing or openings.
- Checking against an apartment's shell or a composition placement (already refused by `room_fit` / `compose_room`).

## Decisions

1. **One helper, two readers.** `house_file.size_warnings(room, overall) -> list[str]` returns plain sentences:
   - `h > room.height_mm + 1` → "Too big for {room}: {h} mm tall, the ceiling is {ceiling} mm.";
   - `w > longest_wall + 1` → "Too big for {room}: {w} mm wide, the longest wall is {wall} mm.".
   The longest wall is the longest edge of `corners_mm` (consecutive corners, closing edge included). The 1 mm tolerance matches `room_contract`'s `_TOL` spirit. Room names are owner text and are neutralised where they enter a prompt; notices are UI text and are rendered as text.
2. **Build notice.** `post_build` reads `spec.json`'s `overall` and the piece's room in its own session, and `build_text` takes an optional `warnings` list appended after "is built.". Any error reading them logs and posts the notice without warnings (the notice must never fail, as today).
3. **Inspector.** `describe_version` adds `size_warnings: list[str]`, computed the same way for a version with a `spec.json`; `InspectorView` shows them as an amber text line under the title. The type is added in `api.ts`.
4. **Wording for Intake.** `intake.md`: "the purpose, the piece's rough size and height, the style and the budget"; the limit only when the owner gives one; never ask for it.

## Risks / Trade-offs

- [Longest wall is lenient for L-shaped rooms] → a piece can still be too wide for the wall it ends up on; `room_fit` catches that at placement. Recorded as TODO(user).
- [Notices of past builds have no warning] → only new builds get it; the inspector shows it for every version.
