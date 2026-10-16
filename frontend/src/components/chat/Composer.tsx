import { useEffect, useId, useRef, useState } from "react";
import { api, type Upload } from "@/lib/api";
import { FieldError } from "@/lib/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { PendingAttachment } from "./Attachment";

export const ATTACH_LABEL = "Add a plan, photo, design or note";
const ACCEPTED = "image/png,image/jpeg,application/json,.json,.md,.txt,text/markdown,text/plain";

function message(error: unknown): string | null {
  return error instanceof Error ? error.message : null;
}

export const EDIT_WARNING =
  "Sending replaces this message and the replies after it. Builds or versions already made stay.";

/**
 * One message as one turn. `onSend` runs the turn and resolves to its refusal in words, or
 * `null`; a refused message and its files are given back to the owner. While a turn runs,
 * Stop takes Send's place. With `editing`, the latest message's text is put in the box
 * and sending replaces it (`onCancelEdit` leaves it as it was). `compact` (the "Piece, room and chat
 * above" layout) puts a "You:" label, the box and Send on one row, and the rest below it
 * (workspace-chat-above-layout).
 */
export function Composer({ threadId, running, onSend, onStop, editing = null, onCancelEdit, compact = false }: {
  threadId: string;
  running: boolean;
  onSend: (text: string, uploads: Upload[]) => Promise<string | null>;
  onStop?: () => void;
  editing?: { text: string } | null;
  onCancelEdit?: () => void;
  compact?: boolean;
}) {
  const boxId = useId();
  const [text, setText] = useState("");
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [error, setError] = useState<string | null>(null);
  const files = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      setText(editing.text);
      setError(null);
    }
  }, [editing]);

  async function attach(list: FileList | null) {
    setError(null);
    for (const file of Array.from(list ?? [])) {
      try {
        const added = await api.upload(threadId, file);
        setUploads((current) => [...current, added]);
      } catch (refused) {
        setError(message(refused));
      }
    }
    if (files.current) files.current.value = "";
  }

  async function submit() {
    const body = text.trim();
    if (!body || running) return;
    const sent = uploads;
    setText("");
    setUploads([]);
    setError(null);
    const refused = await onSend(body, sent);
    if (refused !== null) {
      // The unanswered message is not kept: give the owner their words back.
      setText(body);
      setUploads(sent);
      setError(refused);
    }
  }

  const pending = uploads.length > 0 && (
    <div className="flex flex-wrap gap-2">
      {uploads.map((u) => (
        <PendingAttachment
          key={u.upload_id}
          upload={u}
          onRemove={() => setUploads((current) => current.filter((c) => c.upload_id !== u.upload_id))}
        />
      ))}
    </div>
  );
  const editWarning = editing && (
    <div className="flex flex-wrap items-center gap-2 text-sm" role="note">
      <span>{EDIT_WARNING}</span>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => {
          setText("");
          onCancelEdit?.();
        }}
      >
        Cancel edit
      </Button>
    </div>
  );
  const box = (
    <Input
      id={boxId}
      aria-label="Message"
      value={text}
      placeholder="Describe what you want…"
      disabled={running}
      className={cn(compact && "min-w-0 flex-1")}
      onChange={(event) => setText(event.target.value)}
    />
  );
  const sendOrStop =
    running && onStop ? (
      <Button type="button" variant="outline" onClick={onStop}>Stop</Button>
    ) : (
      <Button type="submit" disabled={running || !text.trim()}>{editing ? "Send edit" : "Send"}</Button>
    );
  const attachControl = (
    <Label className="cursor-pointer text-sm underline">
      {ATTACH_LABEL}
      <input
        ref={files}
        type="file"
        accept={ACCEPTED}
        multiple
        className="sr-only"
        aria-label={ATTACH_LABEL}
        disabled={running || Boolean(editing)}
        onChange={(event) => void attach(event.target.files)}
      />
    </Label>
  );

  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      {compact ? (
        <>
          <div className="flex items-center gap-2">
            <Label htmlFor={boxId} className="shrink-0 font-heading font-semibold">You:</Label>
            {box}
            {sendOrStop}
          </div>
          {editWarning}
          {pending}
          {attachControl}
        </>
      ) : (
        <>
          {pending}
          {editWarning}
          {box}
          <div className="flex flex-wrap items-center gap-2">
            {sendOrStop}
            {attachControl}
          </div>
        </>
      )}
      <FieldError message={error} />
    </form>
  );
}
