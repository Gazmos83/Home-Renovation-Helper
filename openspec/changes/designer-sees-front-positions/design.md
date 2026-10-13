## Context

`piece_note` (`app/agent/prompts.py`) already renders the latest version's document for the Designer, with each module's fronts as `describe_fronts` text (type, count, height, opening). `derive.front_layout` places fronts: each entry takes its height from the module's top downward, so entry order is top to bottom. `derive.shelf_centres(module, t)` gives each shelf's centre above the module's bottom for a board thickness `t`. The prompt carries no front position, so the model reads the brief.

## Decisions

1. **Derive, do not store.** Positions come from `front_layout` and `shelf_centres` at prompt time, so they cannot drift from the build and no spec or schema field is added.
2. **Per entry, in words.** Each front gets "at the top / at the bottom / between, A–B mm above the module's bottom; covers shelf 2 and 3 (from the bottom)" or "covers no shelf". A shelf is covered when its centre lies inside the entry's span. `t` is the module carcass slot's `thickness_mm`, else 18.
3. **Revision summaries unchanged.** `describe_fronts`, also used for the before and after lines of a revision, stays as it is; the position is added only to the piece note.
4. **Fail quiet.** A `DeriveError`, missing key or odd value leaves that module's line as before.
5. **Precedence stated in the label** and in `designer.md`.

## Risks / Trade-offs

- Folded modules place fronts through the same layout, so bounds may be approximate; the text says "spans" not exact edges.
- More words per module in the Designer's prompt; kept to one clause per front.
