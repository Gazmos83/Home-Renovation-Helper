## 1. New versions of an existing piece

- [x] 1.1 Add `rebuild_piece` to `plugins/revise_package/` (manifest `tools`, the tool with preview and run, subject `rebuild`), per design decision 1. Check: `tests/test_designer_tools.py` (or the revise tests) covers:
  - the preview text;
  - `yes` creating version 2 with v1's design, the change line `rebuilt unchanged from version 1`, a queued build and a bound thread;
  - `no` creating nothing;
  - an unknown id refused;
  - version 1's folder unchanged.
- [x] 1.2 Add `import_design_version` to `plugins/design_import/` (subject `import_version`), and change `import_design`'s two refusals to point at it, per design decision 2. Check: `tests/test_design_import*.py` covers:
  - an import as v2 with the change line `imported from murphy-bed.json, replacing version 1`, bound and queued;
  - a conversation bound to another piece refused;
  - an unknown piece refused;
  - an image or another conversation's upload refused;
  - an invalid file quoted inside the delimiters;
  - `no` creating nothing;
  - the reworded refusals for an id in use and a bound conversation.
- [x] 1.3 Update `designer.md` (when to rebuild, when to import as a version) and `foreman.md` (a new version, rebuild or updated file for an existing piece goes to the Designer; "draft" is a render tier). Check: the instruction-loading tests pass and the plugin listing shows both new tools under their plugins.

## 2. Routing and empty answers

- [x] 2.1 `load_house` sets `piece_named`, and `foreman()` lets a Designer choice stand in a thread without a piece or brief when it is set, per design decision 3. Check: Foreman routing tests with a scripted decision:
  - "Revise it" after a reply naming `murphy-bed` goes to the Designer;
  - "revise it" with no piece named goes to Intake;
  - an image turn still goes to Intake.
- [x] 2.2 Retry an empty specialist answer once, then reply with the fixed sentence, per design decision 4. Check: tests with a fake model:
  - empty then text gives the text as the only new assistant entry;
  - empty twice gives the fixed sentence naming the role;
  - both calls are recorded as usage.

## 3. Delete a conversation

- [x] 3.1 Add the running-turn set and lock in `app/api/chat.py` `_run`, and `house_file.delete_thread`. Check: unit tests show the set is cleared after a turn that raises, and that `delete_thread` removes the row, upload records and tool settings while pieces, versions, reviews and render runs stay.
- [x] 3.2 Add `DELETE /chat/threads/{id}`: 404 for an unknown thread, 409 `turn_running`, the checkpointer delete first with 503 on failure and nothing touched, then the row and the upload directory, answering 204. Check: `tests/test_chat_api.py` covers:
  - deleting a thread with a piece and two uploads: thread read 404, uploads 404 and files gone, piece and versions still listed;
  - 409 while a turn is marked running;
  - 503 when the checkpointer delete raises, with the row kept;
  - 404 for an unknown id;
  - 401 without a session.
- [x] 3.3 Add `api.deleteThread` and, on `Conversations.tsx`, a delete action with an inline confirmation (name, pieces kept, cannot be restored), a refusal shown beside the entry, and the list refreshed. Check: `Conversations.test.tsx` covers confirm (the entry is removed), cancel (no request) and a 409 shown beside the entry. `pnpm lint` passes.

## 4. studio-chat-polish

- [x] 4.1 Narrow `studio-chat-polish` per design decision 6:
  - its proposal's Delete bullet points here;
  - its homeowner-chat delta's running-turn sentence becomes the 409 refusal;
  - tasks 1.2, 4.2, 8.2, 8.4 and 9.1 drop their delete parts.

  Check: `openspec validate studio-chat-polish --strict` passes, and a search of its `tasks.md` finds "delete" only in references to this change.

  Done 2026-10-07: the proposal, design §4, tasks 1.2, 4.2, 8.2, 8.4 and 9.1, and the homeowner-chat running-turn sentence now point here. `openspec validate studio-chat-polish --strict` still fails, but not because of these edits. Its plan-uploads delta predates `package-import`: its MODIFIED texts leave out design files and four current scenarios, and archiving it as it stands would drop design uploads from the spec. That rebase is a content decision for `studio-chat-polish`'s own apply; it is recorded here and was not done. Its studio-ui note (based on the unarchived `studio-conversation`) is an info, not an error.

## 5. Verification

- [x] 5.1 Full suites. Check: in `backend/`, `uv run ruff check .` and `uv run pytest -m "not slow"`, never two pytest processes at once; in `frontend/`, `pnpm lint`, `pnpm test` and `pnpm build`.
- [x] 5.2 Browser check on a scratch database and render root, with real models and the owner's 8000 and 5173 servers untouched. No render is needed; builds are headless with no tier. Steps:
  1. Create a piece in conversation A.
  2. In conversation A, ask for it again as a new version without changes, answer `yes`, see version 2 built with `front.png` and open its inspector.
  3. In a new conversation B, attach the downloaded design of version 2, ask for it to become the next version, answer `yes`, and see version 3.
  4. In a new conversation C, after the Designer names the piece, answer "Revise it: rename it to …" and see the Designer answer.
  5. Delete conversation B from the list after the confirmation, and confirm the piece and all versions are still on the Pieces page.

  Record the steps and results under this task.

  Browser pass 2026-10-07, with real OpenRouter models. Scratch DB `home_renovation_check`, with the render benchmark copied read-only. Backend on 8100 and Vite on 5180, with the render and upload roots in the scratchpad. Headless Chrome through Playwright; the owner's 8000 and 5173 servers were not touched. No render was started.
  1. Conversation "Wall shelf A": brief Yes, then `create_piece` Yes. `wall-shelf` v1 was built with nine files, including the three views.
  2. "Please make a new version of the wall shelf without any changes" gave the Designer's `rebuild` card ("Rebuild wall-shelf as version 2, unchanged from version 1…"). On Yes, v2 was built with an `input.json` identical to v1's and the change line `rebuilt unchanged from version 1`. The panel showed "Inspect version 2".
  3. "Download design (version 2)" from the Pieces page saved `wall-shelf-v2.json`. In new conversation "Import B", attaching it with "Import it as its next version" gave the `import_version` card ("Import wall-shelf-v2.json as wall-shelf version 3, replacing version 2's design"). On Yes, v3 was built with the change line `imported from wall-shelf-v2.json, replacing version 2`, and B was bound to `wall-shelf`.
  4. In new conversation "Routing C" (no piece, no brief), "Which modules and shelves does wall-shelf have?" was answered by the Designer. "Revise it: rename it to Hall wall shelf." was then answered by the Designer with a `revise` card, not by Intake. I answered No.
  5. On the Conversations page, "Delete Import B" showed the confirmation (pieces and renders kept, cannot be restored), and Delete removed the entry. In the database the thread row, its upload row and every `chat:<id>` checkpoint and write were gone, and the upload folder was removed. The Pieces page still lists `wall-shelf` versions 1–3.

