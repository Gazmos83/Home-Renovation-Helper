import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../lib/api";
import { Button } from "@/components/ui/button";

/** The conversation's "decisions so far" note: read it, correct it, or compress now
 * (conversation-memory-settings). Never shows tokens, budgets or models. */
export function DecisionsNote({ threadId }: { threadId: string }) {
  const queryClient = useQueryClient();
  const key = ["conversation-note", threadId];
  const note = useQuery({ queryKey: key, queryFn: () => api.conversationNote(threadId) });
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const done = (value: Awaited<ReturnType<typeof api.conversationNote>>) => {
    setError(null);
    setDraft(null);
    queryClient.setQueryData(key, value);
  };
  const save = useMutation({
    mutationFn: (text: string) => api.saveConversationNote(threadId, text),
    onSuccess: done,
    onError: (e: Error) => setError(e.message),
  });
  const compress = useMutation({
    mutationFn: () => api.compressConversation(threadId),
    onSuccess: done,
    onError: (e: Error) => setError(e.message),
  });

  if (!note.data) return <p className="text-sm text-muted-foreground">Loading…</p>;
  const text = note.data.note;
  return (
    <section className="space-y-3" aria-label="Decisions so far">
      <h2>Decisions so far</h2>
      <p className="text-sm text-muted-foreground">
        {note.data.package_id ? `For ${note.data.package_id}. ` : ""}
        Earlier parts of a long conversation are sent to the assistants as this note. The full conversation stays
        here.
      </p>
      {draft === null ? (
        <>
          {text ? (
            <p className="whitespace-pre-wrap text-sm">{text}</p>
          ) : (
            <p className="text-sm text-muted-foreground">There is no note yet.</p>
          )}
          {note.data.owner_edited && <p className="text-xs text-muted-foreground">Corrected by you.</p>}
          <div className="flex flex-wrap gap-2">
            {text && (
              <Button type="button" variant="outline" size="sm" onClick={() => setDraft(text)}>
                Correct
              </Button>
            )}
            <Button type="button" size="sm" disabled={compress.isPending} onClick={() => compress.mutate()}>
              {compress.isPending ? "Compressing…" : "Compress now"}
            </Button>
          </div>
        </>
      ) : (
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate(draft);
          }}
        >
          <label htmlFor="decisions-note" className="text-sm font-medium">
            Your correction
          </label>
          <textarea
            id="decisions-note"
            className="w-full rounded-md border px-3 py-2 text-sm"
            rows={8}
            maxLength={8000}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={save.isPending || !draft.trim()}>
              Save
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setDraft(null)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </section>
  );
}
