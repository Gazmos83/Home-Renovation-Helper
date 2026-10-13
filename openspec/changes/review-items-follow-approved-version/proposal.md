## Why

The chat showed the owner an "expected" measurement taken from version 1, after later versions were approved. The "Open review items" the Designer and Intake receive come from the newest review of the piece, whatever version it was of. A review of version 1 therefore keeps putting its expected figures (taken from the brief or the first spec) into the prompt after the owner has approved a different version, and the model repeats them.

## What Changes

- The open review items placed in the prompt come only from a review of the piece's current version: the approved version when one is approved, otherwise the latest version. If that version has no review, none are shown.
- Each item is labelled with the version it is about, so the model can say which version it is describing.
- Approving or unapproving a version changes which review is shown from the next turn, with no action by the owner.
- Reviews and their items are not deleted, edited or closed; the Reviews records and the owner's own status changes are untouched.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `house-file`: the open review items in the conversation's context follow the current version instead of the newest review.

## Impact

- Backend: `house_file.latest_open_items` and its call in `foreman.py`; the "Open review items" lines in `prompts.py`; tests.
- The Project panel's open-items read is a separate path and is not changed here.
- Not covered: a new review of a later version can still take its "expected" figures from the brief's old measurements. That is the separate brief question and is not changed by this.
