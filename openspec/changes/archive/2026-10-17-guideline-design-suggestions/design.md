## Context

The Designer already has `search_guidelines`, which searches the `guideline` category: uploaded PDFs, checked-in publications, owner notes and hardware data sheets. It returns up to five passages wrapped as untrusted content, or a plain "nothing matched". Its instructions limit it to rules and numbers (`designer.md`, the `search_guidelines` rule). The confirmed brief carries a style, and the Designer's context carries templates only while there is no active build ("The Designer gets templates only for a new piece"). `create_piece` previews and waits for `yes`.

## Goals / Non-Goals

**Goals:**
- Use the existing tool and confirmation flow; change only the Designer's instructions.

**Non-Goals:**
- No code gate that forces the search before `create_piece`, no new tool, and no schema field for style.
- No suggestions on revisions, imports or rebuilds.
- No ranking or filtering of passages beyond what `search_guidelines` already does.

## Decisions

- **Instruction rule, not a code gate.** A code gate on `create_piece` would have to tell "owner declined suggestions" and "nothing matched" apart from "the Designer skipped the search", and that needs conversation state the tool does not have. The behaviour is advisory, and the owner still confirms every document, so a wrong skip costs a missed idea, not a wrong piece. Alternative considered: a `suggestions_offered` flag checked by `create_piece`; rejected as new state for a soft behaviour.
- **Suggestions in the chat reply, answered in the next message.** `ask_owner` caps question text at 200 characters, which a cited suggestion often exceeds. A plain reply also keeps the citation readable. The reply ends the turn without `create_piece`, as the change-list rule already does for revisions.
- **Accepted means confirmed.** The existing rule "use only sizes the owner confirmed" stays. A number in an accepted suggestion becomes confirmed by that acceptance, so nothing new about dimensions is needed.
- **Advice only is not a generator-extension request.** A fabric or wall colour is not something the piece's schema should grow to hold, so recording it would fill the house file with requests the workshop cannot act on.

## Risks / Trade-offs

- [The model skips the search or quotes from memory] → The rule names the trigger and the "found no style guidance" wording, the instruction test pins that wording, and the owner sees every document before `yes`.
- [Letter-spaced headings in the Gotcha Covered PDF ("C ON T E N TS") weaken section citations] → The Designer cites the section text as the passage gives it. Re-ingesting cleaner text is the owner's choice, outside this change.
- [An extra round trip before the first draft] → The owner can say "go straight to the draft". At most three suggestions keeps the reply short.
