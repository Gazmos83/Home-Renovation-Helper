## Context

See proposal.md (Why). Current state:

- A piece is a `pieces` row plus `docs/renders/<id>/v<N>/`. A version folder holds `input.json`, the bare custom-build design. It also holds the frozen hardware inputs, read with `storage.read_hardware_inputs`. `service.create_version` writes both, marks the build queued and starts it.
- `create_piece/tool.py` has `checked_new_id` (valid and unused id) and `create_and_record` (version, piece and version records, then bind the thread). These are built for a Designer turn in the current conversation.
- `POST /chat/threads` with `package_id` creates a conversation bound to a piece (`house_file.create_thread`). The Pieces page uses it for "Start conversation".
- The matched-design reply (`DESIGN_MATCHES_PIECE` in `foreman.py`) comes from `delete-piece`, which is applied but not archived. `_pending_design(messages)` already finds the newest design file in any owner message. The Designer's handoff note (`handoff_design`) already tells it to call `import_design` with an upload id.

## Goals / Non-Goals

**Goals:**
- One duplicate service, used by both the route and the tool, so the two cannot drift.
- "Keep both" decided in code, from the previous fixed reply plus the owner's words, never by a model.

**Non-Goals:**
- Duplicating a room composition or an apartment shell.
- Copying renders, approvals, reviews, verdicts, pricings or saved places. The copy is a fresh piece with a known design.
- Duplicating a version into an existing piece. That is what revise and import-as-next-version already do.

## Decisions

1. **Service `app/packages/duplicate.py`.** It has one entry point: `duplicate(session, deps-like inputs, source_id, version, name, new_id) -> {package_id, version, thread_id}`. It checks every refusal from the spec before anything is written:
   - the source version exists and has an `input.json`;
   - the id is free (same check as `checked_new_id`);
   - the name is new (ignoring case);
   - the design passes `validated_spec`.

   It then sets `design["name"] = name` and calls `service.create_version` with the source's hardware inputs. It records the piece with the source's `room_id` and `brief`, records v1 with the change line, and creates the bound thread with title = name. The DB writes go in one commit. The route passes its `_start_build`; the tool passes `ctx.deps.start_build` wrapped in `notices.follow_build` for the new thread.
   *Alternative:* reuse `create_and_record`. Rejected, because it binds the current conversation and freezes new inputs.

2. **Hardware inputs are copied, not re-frozen.** Copying keeps the copy's cut list and drilling list identical to the source version. Re-freezing could quietly change hinge counts when the rules have moved on. A source version with no frozen inputs (older versions) is copied without them, which is how such a version was built.

3. **Schema validation only, no design-rule refusal.** The source was already accepted, so a duplicate runs the same checks as `PUT /packages/{id}/spec`. The tool's preview still lists design-rule warnings from `piece_outcome`, as `create_piece` does, but those warnings do not refuse.

4. **Id derivation.** The default id is `storage.apartment_slug(name)`. When the tool is called without an id and that id is taken, the service appends `-2`, `-3` and so on, and the preview shows the result. The Pieces form always sends an id: it prefills the slug and follows the name until the owner edits it, and a taken id comes back as the refusal for the owner to change. An explicit id is never changed. A taken explicit id is refused.

5. **Route `POST /packages/{package_id}/duplicate`.** Body `{version, name, package_id}`, response 202 `{package_id, version, status, thread_id}`. Refusals use the existing `refused(...)` helper: 404 for an unknown source or version, 409 `package_exists` / `name_taken`, 422 for validation, and `require_generation` for no Blender. The form's prefilled id comes from a small helper in the frontend that mirrors the slug rule. The server stays authoritative.

6. **Tool `duplicate_piece`.** It lives in plugin `backend/plugins/duplicate_piece/` with role designer, enabled by default and toggleable. It follows the `create_piece` preview/run shape. It does not call `refuse_new_piece_when_bound`, because the current conversation is never rebound. The output text names the copy and gives the conversation path `/studio/workspace/<thread_id>`. The house-file slice rule still holds: the current conversation's prompt gets nothing of the copy beyond that one line.

7. **"Keep both" handoff.** In the Foreman's state step, `keep_both` is set when two things hold:
   - the conversation has no piece, and the previous AI message starts with the fixed prefix "The attached design";
   - the newest owner message contains "keep both", or "beide behalten" (case-insensitive).

   The Foreman then routes to the Designer with `handoff_design = _pending_design(messages)` and a note. The note says the owner wants to keep both, gives the owner's words as data inside the usual neutralised quote, and tells the Designer to call `import_design` with `name` set to the new name the owner gave, or to ask for one. A model never decides whether the reply was "keep both". Only the code match does that.

8. **`import_design` gains `name: str | None`.** After `parse_import`, a given name replaces `design["name"]` and is checked against existing piece names. A name clash refuses with the reason. The rest of the import is unchanged. The new name also makes the default `package_id` the model proposes, but the model still passes the id explicitly as today.

## Risks / Trade-offs

- [The owner writes "keep both" in other words, such as "both please"] → The conflict reply quotes the exact words "keep both". Anything else gets the normal Foreman routing, which can still reach `import_design` with a name. The handoff note only makes that path reliable.
- [The source design fails the current schema after a schema change] → It is refused by field name, as the spec says. That becomes a generator-extension request, never a silent fix.
- [A source version is still building] → It is allowed. Only `input.json` and the inputs are read, and both are written before the build starts.
- [Name uniqueness is new] → It applies only to duplicates and to an import given a name. It is not applied to existing pieces or to `create_piece`, so behaviour elsewhere stays the same.

## Migration Plan

No schema migration. Deploy is code-only. To roll back, revert the commit. Copies already made stay as ordinary pieces.

## Open Questions

None.
