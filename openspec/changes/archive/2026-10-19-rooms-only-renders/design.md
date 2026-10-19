## Context

See proposal.md (Why). After `render-now-blueprints-verdict-note` (revised 2026-10-18):
- the piece inspector has no Renders tab, and a piece render's notice is text only;
- the room inspector (Workspace room pane) has "3D view" / "Renders" tabs with "Render version N now";
- every piece render was deleted.

Still in place: `render_turntable` accepts `package_id` and `in_room`; `restyle_render` accepts `slots` (piece looks); the piece pane shows `PieceVariants` with "Use this look"; the Pieces page lists stills with `RenderRating` and piece variants; the Builder's and Foreman's instructions describe piece renders.

## Goals / Non-Goals

**Goals:**
- No agent tool and no Studio page makes a piece render (the Lighting detail pass and the developer HTTP route keep theirs for now).
- The agents say so in plain words and offer the room instead.

**Non-Goals:**
- Moving the Lighting detail pass to rooms (TODO(user), its own change).
- Deleting the piece paths in the headless generators: the detail pass still renders a piece's detail copy.
- Removing `config/looks.yaml`; it stays loaded until the detail pass decides whether it needs looks. TODO(user).

## Decisions

1. **Refuse in the tools, not only in the prompts.** `render_turntable._target` refuses `package_id` and `in_room` before any quote; `restyle_render` refuses `slots`. The tool text is the one sentence the model passes on. Prompt-only rules were rejected: CLAUDE.md asks restrictions to be enforced in code.
2. **The schemas keep the fields for one release.** The argument models keep `package_id`, `in_room` and `slots` so an old prompt gets the plain refusal instead of a schema error naming an unknown field.
3. **Frontend removals are plain deletions.** `PieceVariants` and `keepLookRequest` go from the piece pane; the Pieces page drops its stills, `RenderRating` and variants blocks. `RoomVariants` stays.

## Risks / Trade-offs

- [The owner asks to "render the bench"] → The refusal offers to compose the room with the bench and render the room; the Foreman routes it to the Builder, which explains.
- [Render feedback tables keep rows only for rooms and shells] → Ratings stay possible on room renders later; nothing reads piece ratings any more.

## Migration Plan

None. The piece renders were deleted on 2026-10-18 with a backup outside the repository. Rollback: revert the change.
