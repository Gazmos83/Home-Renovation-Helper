## Context

`render_answer` in `app/engineering/chat.py` builds the reply for every engineering turn: `INSUFFICIENT`, a preliminary-advice line, an optional lookup-off line, owner assumptions, evidence and property lines, `Missing inputs/review: …`, conflicts, a legal note and report JSON. The rejected path returns `INSUFFICIENT` + "Invalid or unsupported engineering answer was rejected." + missing inputs.

`foreman.py` sets `engineering = state["engineering_turn"] OR decision.engineering_question`. `engineering_turn` comes from the code matcher; `engineering_question` from the routing model. The height-question rule (simple-height-question-reply) already overrides the model flag for one narrow message form.

## Decisions

1. **One fixed status sentence, a constant.** `SHORT_STATUS = "Not verified: no engineering check is available, so load capacity, fixings and safety are unconfirmed."` (15 words). It is the first line of every rendered reply and the whole reply on the rejected path. A test asserts it is at most 20 words.
2. **Boilerplate lines go; data lines stay.** Removed from the rendered reply: the not-implemented sentence, preliminary-advice line, lookup-off line, "no applicable evidence" line, missing-inputs list, legal note, and the "was rejected" sentence. Kept: owner assumptions, evidence citations, property values, code-detected conflicts, reports and metadata links — they only appear when real evidence or a report was selected.
3. **`INSUFFICIENT` stays for the model-facing history.** `request_history` still replaces earlier engineering replies with `INSUFFICIENT` before a model sees them; that text is never shown to the owner, so it is unchanged.
4. **Placement overrides the model flag, not the code matcher.** `placement_request(text)`: a placement verb (put, place, move, position, set, stell, platzier, schieb) and a room reference (wall, door, window, corner, Wand, Tür, Fenster, Ecke) or a distance (`\d+ (cm|mm|m)` with away/from/von/Abstand) — and `engineering_intent(text)` is false. In the Foreman, `engineering = state engineering_turn OR (model flag AND NOT placement_request)`. A message that also names an engineering term ("put the wall cabinet on the wall, is it safe?") stays on the engineering path.
5. **No data written.**

## Risks / Trade-offs

- Dropping the missing-inputs list hides what would make a check possible. Chosen by the owner for brevity.
- The placement matcher is a word rule, like the height rule; a rephrased placement ("could v18 sit next to the door?") still depends on the model flag. It can be widened with tests when reported. The alternative — ignoring the model flag entirely and trusting only the code matcher — would fix both reports at once but drop engineering questions the regex misses ("will it sag with books?"); not chosen.
