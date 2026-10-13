## 1. Backend

- [x] 1.1 Add read and save routes for a thread's brief with a Pydantic body; verify purpose required, height and budget ranges, unknown room refused, a running turn refused, and the thread comes from the path.
- [x] 1.2 Save writes the checkpoint brief, the bound piece's brief and (when allowed) the style and budget preferences; verify each, that the Reviewer then reads the new brief, and that a hand-edited height clears the "raised by version" note.

## 2. Frontend

- [x] 2.1 Add `brief`, `piece` and `room` icons to `Rail.tsx`; verify the rail shows six icons and labels when expanded.
- [x] 2.2 Split `ProjectPanel` into Project, Piece and Room panels in `Conversation.tsx`; verify each shows only its content, empty states read "No piece yet." and "No room selected yet.", and the refresh while building still works.
- [x] 2.3 Reword the notices' "Project panel" text in `backend/app/agent/notices.py` (and the `homeowner-chat` delta) to "Piece panel"; update the backend notice tests that quote it.
- [x] 2.4 Update `Rail.test.tsx` and `Conversation.test.tsx` to the new panels; add a test for piece and room kept apart.

- [x] 2.5 Add the Brief panel (form, Save, refusal text, empty state); verify editing and that no internals are shown.

## 3. Agents and room picture

- [x] 3.1 Add the brief's settings to the facts line; verify an edit shows in the next Foreman and specialist prompts and an empty brief adds nothing.
- [x] 3.2 Add `approved_picture` to the room progress and show it in the Room panel; verify it follows the approved version (also an old one) and is absent without one.

## 4. Specs

- [x] 4.1 Update the other requirements that name the Project panel (design-agents, house-file, furniture-packages, studio-ui) in the deltas.

## 5. Verification

- [x] 5.1 `pnpm test`, `pnpm lint` and `pnpm build` pass; browser-check the four flyouts before it counts as done.
