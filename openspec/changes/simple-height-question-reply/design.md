## Context

`foreman.py` takes `engineering = state flag OR decision.engineering_question`; the second is set by the routing model, and for "What's expected height" it was true, so the turn went to the Researcher and `engineering_chat.render_answer` rendered the fixed disclaimer block. The Foreman already has application rules that answer with a fixed text and end the turn (for example a price or product refusal).

## Decisions

1. **A code rule, not a prompt.** A matcher for the short height question runs after the routing decision and before the engineering branch, and ends the turn with the fixed text, like the existing fixed replies. A model flag cannot override it.
2. **Narrow match.** The whole message (ignoring case, punctuation and a leading "what is/what's/tell me") is the question "(the) expected|maximum|max|highest|target height (of the piece)", and `_ENGINEERING` and `kitchen_intents` must not match it. Anything else is unchanged.
3. **Fixed wording**, one constant, tested.
4. **No data written.**

## Risks / Trade-offs

- The reply withholds a height the app already knows (the brief's limit, the approved version's height). Chosen by the owner for simplicity; a later change can state the known figure before asking.
- A rephrased question ("how tall may it be?") is not matched and goes the old way; the rule can be widened with tests when the owner reports one.
