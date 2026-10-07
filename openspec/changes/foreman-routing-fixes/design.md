## Context

See proposal.md for the motivation. The relevant code as it stands:

- **Routing.** `foreman()` in `app/agent/foreman.py` asks the `foreman` slot for a structured `Decision`, then bounds it with code rules for the Builder, the Reviewer and Lighting, plus "no brief and no buildable piece goes to Intake". Nothing sends a room correction to Intake once a brief exists. `instructions/foreman.md` describes `designer` as "the numbers are confirmed and the owner wants a piece designed, changed…", which the model read as covering the room. The checkpointer shows the corrections at messages 19–25 and 31–33 of thread `daf9cc86…` routed to `designer`.
- **Refusal.** `tools_node` answers any call whose name is not in `bound_for(state)` with the constant `NOT_AVAILABLE_NOTE = "this tool is not available to you"`. The model saw `record_brief` in the history and called it. The constant did not say who owns the tool, so the model invented "won't take an update".
- **History.** `chat.history` keeps `AIMessage`s only when `message.content and not message.tool_calls`, so 4 of the 43 assistant messages in that thread were dropped. When a confirmation is answered, its interrupt payload is consumed on resume and survives nowhere in `messages`.
- **Overlapping changes.** The requirement "The Foreman routes each turn to one specialist" is MODIFIED by two unarchived changes, `photoreal-detail` (the newest text, with Lighting) and `pricing-researcher` (an older text). Neither touches `homeowner-chat`'s history behaviour. `studio-conversation` adds homeowner-chat requirements, but not on history.

## Goals / Non-Goals

**Goals:**
- Route room corrections to Intake, with code backing the prompt where a signal exists.
- Make every refused tool call honest and actionable for the model.
- Show the owner every reply and every answered confirmation, without exposing tool traffic.

**Non-Goals:**
- Rendering Markdown, chat layout, streaming and forms. Those belong to the planned `studio-chat-polish` change.
- Handing a turn over between specialists mid-turn. One specialist per turn stays as specified.
- Notifying the owner when a build finishes. That would need push or streaming, which belongs to `studio-chat-polish`.

## Decisions

1. **ADDED requirements, not a MODIFIED routing requirement.** Room corrections are written as a new requirement, "Room corrections go to Intake", so this delta does not compete with the two in-flight MODIFIED texts of the routing requirement. Archiving in any order then leaves one coherent spec.
   - *Alternative:* MODIFY the routing requirement on top of `photoreal-detail`'s text. Rejected: archiving `pricing-researcher` afterwards would overwrite it with its older text.
2. **Routing by prompt, plus a code rule for attached images.** The "is this a room correction?" judgement stays with the Foreman's model, through a new `intake` line and an explicit rule in `foreman.md`: "a correction to a room's measurements, angles, openings or ceiling height, or a new plan, goes to `intake` even after the numbers are confirmed or a piece exists". Code adds one cheap, certain rule: a turn whose owner message carries `upload_ids` and whose model choice is `designer` goes to Intake, because only Intake reads plans and photos (its slot has image input).
   - *Alternative:* keyword matching in code ("wall", "corner", "°"). Rejected: brittle, and it would misroute piece changes such as "make it 2206 mm wide".
   - *Risk noted below:* a photo attached for a piece change also goes to Intake. Intake can then say so, and the next text-only message reaches the Designer.
3. **Refusal text built from the instruction headers.** At graph build, compute `owners: dict[tool, list[specialist]]` from `loaded[name].tools` (shared tools such as `record_render_feedback` list both owners). `tools_node` picks one of three texts:
   - the specialist's own header names the tool but it is not bound: "`cut_list` is switched off in this conversation's tools. Nothing was done."
   - another specialist owns it: "`record_brief` belongs to Intake, not to you. Nothing was done or saved."
   - no one owns it: "There is no tool `x`. Nothing was done."

   Each text is a fixed template filled with the tool and role names, and none of them is model-written. `NOT_AVAILABLE_NOTE` is replaced by these templates.
4. **One shared instruction sentence.** Each specialist's instruction file gains the same sentence: "If a tool result says nothing was done, tell the owner plainly that nothing was saved or changed and why; never say a tool failed or would not take an update." `test_instructions.py` checks that every file contains it. The instruction loader's composition is unchanged.
5. **Answered confirmation stored on the gated tool's result.** In `tools_node`, when `first_gated` raised a `Confirmation` and an answer came back, the `ToolMessage` for that call gets `additional_kwargs={"confirmation": {"subject", "summary", "answer", "reason"}}`. The checkpointer persists it. `chat.history` turns it into a `{"role": "confirmation", "text": …}` entry, with the text formatted by code as "subject: summary — answer (reason)". `MessageOut.role` becomes `Literal["owner", "assistant", "confirmation"]`.
   - *Alternative:* add a visible `AIMessage`. Rejected: it would enter the model's context as words the model never said.
   - *Alternative:* a new table. Rejected: a migration for one line.
6. **History rule.** Keep an `AIMessage` whenever its text, stripped, is non-empty, whether or not it has tool calls. Skip `ToolMessage`s except to read the confirmation kwargs. A whitespace-only message (the `'\n\n'` beside a tool call seen in the thread) stays hidden.
7. **The Studio shows the new role.** `Conversation.tsx` renders a `confirmation` entry as a muted, bordered line ("Confirmed: brief — yes"). Its styling stays minimal, because `studio-chat-polish` restyles the whole view.

## Risks / Trade-offs

- [The model still misroutes a text-only correction] → The Intake rule sits in `foreman.md`. The honest refusal (decision 3) turns any remaining misroute into a plain "nothing was saved; Intake handles rooms" instead of a silent loss. The scenario is pinned with a scripted Foreman decision in `test_foreman.py`, which tests the code path and the prompt text, not the model's judgement.
- [The upload rule sends a piece photo to Intake] → Intake reads photos for materials and position already. The cost is one extra turn, and no data is lost.
- [Older checkpoints have no confirmation kwargs] → Their answered confirmations simply produce no entry. Nothing is migrated or broken.
- [The confirmation text could carry internals] → The summary is the one already shown to the owner on the card. The no-internals test is extended to the history.
