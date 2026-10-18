## Why

In the 2026-10-15 end-to-end review the owner noted that a confirmed change stays in the conversation as one long grey line. For example, "Answered: compose_room: Room Wohnen: 4 item(s) … — yes" repeats the whole summary and starts with the tool's internal name. The owner wants it shrunk to a plain title such as "Composing room", with a dropdown, and a room change's calculations listed in a table. The owner decided on 2026-10-18 that this applies to every confirmation, not only room changes, and that a raw tool name such as `compose_room` is never shown.

## What Changes

- **A plain title per confirmation.** Each confirmation subject gets a fixed homeowner title, composed by code:

  | Subject | Title |
  |---|---|
  | `compose_room` | Composing room |
  | `revise` | Revising piece |
  | `rebuild` | Rebuilding piece |
  | `create_piece` | Creating piece |
  | `import_design` | Importing design |
  | `import_version` | Importing version |
  | `brief` | Confirming the brief |
  | `plan` | Reading the plan |
  | `room` | Confirming the room |
  | `decisions` | Changing decisions |
  | `final_render` | Final render |
  | `detail_pass` | Detail pass |
  | `detail_render` | Detail render |
  | `remnant` | Recording a remnant |
  | `version_verdict` | Rating the version |
  | `render_feedback` | Rating the render |
  | `assessment_inputs` | Engineering inputs |

  An unknown subject is shown as "Confirmation", never by its subject.
- **The answered confirmation is collapsed.** In the conversation it becomes one compact row: the title and the answer ("Composing room · Yes", "Revising piece · No"), with the reason when one was given. A dropdown button opens the summary the owner was shown. A reload shows it collapsed again.
- **Room changes show their calculations as a table.** A `compose_room` confirmation carries one table row per item: item, kind, size W × D × H (mm), placement (wall and offset, or free), centre x and y (mm) and rotation. The rows come from the positions the composition check already computed. The table is shown in the dropdown, above the comparison with the previous version and any design-rule warnings. A confirmation answered before this change has no table and shows its summary text only.
- **The pending card uses the same title.** "Confirm: compose_room" becomes "Confirm: Composing room". A pending room change shows the same table above its Yes and No buttons.
- **Thread history carries the title and the table.** A `confirmation` entry gains `title`, `answer`, `reason` and an optional `table` (`columns`, `rows`). `text` stays for compatibility.
- **Assumption, TODO(user) for review:** gaps between items and distances to walls other than the placement wall are not computed today, so they are not in the table.

Ladder: none of the three steps. This is chat presentation and the `compose_room` preview, with no schema or generator change. Agents touched: none directly. Code composes the titles and the table, and no model sees them. The `compose_room` preview (Designer's tool) adds its table to the confirmation. The **render guard** and the **bpy allow-list** are **not affected**.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: history `confirmation` entries carry a plain title, the answer, the reason and an optional table; no internal subject reaches the owner.
- `studio-ui`: the pending confirmation card shows the plain title (and a room change's table), and an answered confirmation is shown collapsed with a dropdown.
- `room-composition`: a composition proposal's confirmation carries its calculations as a table.

## Impact

- `backend/app/agent/tools/base.py`: `Confirmation` gains an optional `table`.
- `backend/app/agent/chat.py`: a `CONFIRMATION_TITLES` map, the history entry fields (`_confirmation_line` is kept for `text`), and `Pending` exposing `title` and `table`.
- `backend/app/agent/foreman.py` (around line 1340): the answered record keeps `table`.
- `backend/app/api/chat.py`: `PendingOut` and `MessageOut` gain `title`, `answer`, `reason` and `table`.
- `backend/app/compositions.py`: `Proposal` gains `table`, built where `propose` builds the summary lines. `backend/plugins/compose_room/tool.py` passes it on.
- `frontend/src/lib/api.ts`: the types. `frontend/src/routes/Conversation.tsx`: `ConfirmationCard` heading and table, and a new collapsed `AnsweredConfirmation` row in place of the "Answered:" paragraph. The table reuses the shadcn `Table` that `AnswersTable` already uses.
- Tests:
  - `backend/tests/test_chat_api.py` history entries (line 583);
  - a titles test listing every `Confirmation(subject=…)` in `backend/plugins`;
  - the compose_room table;
  - `frontend/src/routes/Conversation.test.tsx` (line 625).
- Relation to `short-answers-show-maths`: the collapsed row uses the same outline-button disclosure pattern as its "Show the maths" button. Neither change edits the other's requirement text.
