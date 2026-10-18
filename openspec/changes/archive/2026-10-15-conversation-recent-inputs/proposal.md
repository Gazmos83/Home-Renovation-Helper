## Why

An agent call sends the conversation's whole history until it passes the compression trigger, which is 70 % of the model's usable budget. In the murphy bed conversation (2026-10-15) that is about 14,000 tokens of history for every model call, and a Designer turn often makes several calls. The owner finds that too much and asked (2026-10-15) for recall limited to the last 5 inputs, with older history kept only in compressed form. Today's settings cannot do that: the trigger cannot go below 50 %, and "recent turns always kept" protects turns but never drops older ones.

The same conversation also loops. After "Will the bridge be structurally stable if the dividers are removed?", every later message ("Keep and shorten the dividers.") gets the same reply: "Not verified: no engineering check is available …". An engineering turn marks only its replies and tool results, not the owner's question. Later routing calls therefore still see the question without its answer, and the routing model flags each new turn as engineering again. On an engineering turn the agent must answer in the fixed engineering format, so the Designer's ordinary reply is replaced by the status line every time. The owner asked (2026-10-15) to fix this in the same change.

## What Changes

- **New memory setting "Recent inputs sent in full"** (`recent_inputs`, 0–20).
  - When it is above 0, an agent call sends only the exchanges from the Nth most recent owner input onward, plus the current turn.
  - Every older exchange is always replaced by the conversation's summary note: the active build's note, refreshed when needed, as today. This applies however much room is left in the budget.
  - 0 keeps today's behaviour, where the trigger decides.
- **Default 5.** **BREAKING** (request content): with no setting changed, a conversation with more than 5 earlier owner inputs now sends the summary note in place of the older exchanges. The stored conversation is unchanged, and so is the owner's chat view.
- **The routing call follows it too.** The Foreman's routing call also sends only the recent inputs. In place of older exchanges it uses the stored note when one exists, otherwise the shortened-history note. Routing never writes a note.
- **Unchanged:** the trigger still applies inside the recent inputs, so a few very long recent exchanges are still compressed when they pass it. Engineering turns already send only their own exchange. The note length and instructions, the cut-length for tool results, and the untrusted-content wrapping all stay as they are.
- **Stop the engineering loop.** The owner's question on an engineering turn becomes part of the engineering exchange. Later calls leave out the whole exchange, question and answer, so an answered question no longer makes every later turn an engineering turn. Conversations stored before the change recover too: an owner message whose turn has an engineering reply counts as part of the exchange. No stored data changes. A new engineering question is still one.
- **Developer panel:** the Agent Memory tab shows the new setting with its default, refuses values outside 0–20 naming the field, and can reset it.

**Ladder step and agents:** none. This changes what every agent's call is sent, and stops a stale engineering flag from overriding the Foreman's routing. It does not change what any agent may do. **Render guard and bpy allow-list:** not affected.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `token-budget`: fitting gains the recent-inputs limit. Exchanges before it are always replaced by the summary, and the routing call follows the same limit.
- `dev-panel`: the memory settings gain "Recent inputs sent in full".
- `homeowner-chat`: an answered engineering question does not make later turns engineering turns.

## Impact

- Code:
  - `app/agent/memory_settings.py`: the `recent_inputs` field, default 5.
  - `app/agent/budget.py`: `fit`/`prepare` take `recent_inputs`; exchanges before the cut are forced into the summary like `covered_through`.
  - `app/agent/foreman.py`: `prompt_for` passes the setting for agents and the Foreman.
  - `app/engineering/chat.py`: `request_history` treats a turn with any engineering-marked message as an engineering exchange, the owner's question included.
  - Frontend Agent Memory tab: one field.
- Data: none (the memory settings are one JSON operator setting).
- Expected effect (measured, task 5.1): in the murphy bed conversation, a Designer call's history drops from ≈ 13,900 to ≈ 6,200 tokens, and a routing call's from ≈ 8,800 to ≈ 4,600, note included.
- Risk: a detail mentioned more than 5 inputs back survives only if the note keeps it. In the murphy bed conversation, the bridge dividers were described about 6–8 inputs back. The note's default instructions keep figures and decisions per piece, and the owner can raise the setting or edit the note.
