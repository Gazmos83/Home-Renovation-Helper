## Why

Asked "What's expected height", the chat answered with the full engineering block: "NOT VERIFIED. Numerical engineering calculation is not implemented…", the "preliminary design advice" line, "engineering lookup is switched off", a list of missing inputs and a legal note. The Foreman's routing model flagged the question as an engineering question (its flag is set for strength, load, deflection, anchorage or safety, and it over-reached for a height), and the engineering path renders that block in code. The owner wants a simple answer: say the height is not verified, and ask what the height should be.

## What Changes

- A message that only asks what the expected, maximum or highest height is gets one fixed reply: "The height is not verified. What should the height be?" It is chosen by an application rule before any specialist runs, so no engineering text, no tools and no model call for that answer.
- The rule is narrow: it matches the short question form only. A message that names strength, load, deflection, anchorage, safety, a kitchen part or any other engineering word, or asks about another dimension, is routed as before.
- Nothing is written to the house file, the brief or the note; the owner's reply is read like any other message.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: a plain question about the expected height gets a short fixed reply instead of the engineering block.

## Impact

- Backend: `foreman.py` (an application rule beside the existing fixed replies), a small matcher beside `engineering/chat.py`, tests.
- No frontend, migration or prompt change. The engineering path itself is unchanged for real engineering questions.
- Trade-off: the reply does not quote the brief's limit or the approved version's height even when the app knows it; the owner chose a simple prompt for the figure.
