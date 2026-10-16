import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { api, ApiError, type Verdict } from "@/lib/api";
import { FieldError } from "@/lib/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * The owner's verdict on one piece version (version-verdict): does it match what they
 * confirmed? A thumbs up or down above the inspector's tabs, whether or not the version is
 * built or rendered. The note field appears only once a thumb is chosen; a thumbs down
 * needs a note before it is saved and stays open until resolved or dismissed. Pressing
 * the chosen thumb again clears the verdict.
 */
type Choice = "matches" | "mismatch";

export function VersionVerdict({ packageId, version }: { packageId: string; version: number }) {
  const queryClient = useQueryClient();
  const key = ["verdict", packageId, version];
  const current = useQuery({ queryKey: key, queryFn: () => api.verdict(packageId, version) });
  const saved = current.data?.verdict ?? null;
  // A thumbs down chosen but not saved yet, waiting for its note.
  const [pending, setPending] = useState<Choice | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [missingNote, setMissingNote] = useState(false);

  const settle = (data: { verdict: Verdict | null }) => {
    queryClient.setQueryData(key, data);
    setPending(null);
    setNote(null);
    setMissingNote(false);
  };
  const give = useMutation({
    mutationFn: ({ verdict, text }: { verdict: Choice; text: string | null }) =>
      api.giveVerdict(packageId, version, verdict, text),
    onSuccess: settle,
  });
  const clear = useMutation({ mutationFn: () => api.clearVerdict(packageId, version), onSuccess: settle });
  const close = useMutation({
    mutationFn: (status: "resolved" | "dismissed") => api.closeVerdict(packageId, version, status),
    onSuccess: settle,
  });
  const failure = give.error ?? clear.error ?? close.error;

  if (current.isLoading || current.error) return null;
  const chosen: Choice | null = pending ?? saved?.verdict ?? null;
  const text = note ?? saved?.note ?? "";

  function choose(verdict: Choice) {
    if (chosen === verdict) {
      if (pending) settle({ verdict: saved });
      else clear.mutate();
      return;
    }
    if (verdict === "matches") give.mutate({ verdict, text: text.trim() || null });
    else if (text.trim()) give.mutate({ verdict, text: text.trim() });
    else setPending("mismatch");
  }

  function saveNote() {
    if (!chosen) return;
    const trimmed = text.trim();
    if (chosen === "mismatch" && !trimmed) {
      setMissingNote(true);
      return;
    }
    if (!pending && trimmed === (saved?.note ?? "")) return;
    give.mutate({ verdict: chosen, text: trimmed || null });
  }

  return (
    <section aria-label="Verdict" className="grid gap-1">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant={chosen === "matches" ? "default" : "outline"}
          aria-pressed={chosen === "matches"}
          aria-label="Matches what I confirmed"
          title="Matches what I confirmed"
          onClick={() => choose("matches")}
        >
          <ThumbsUp aria-hidden size={16} />
        </Button>
        <Button
          type="button"
          size="sm"
          variant={chosen === "mismatch" ? "default" : "outline"}
          aria-pressed={chosen === "mismatch"}
          aria-label="Doesn't match what I confirmed"
          title="Doesn't match what I confirmed"
          onClick={() => choose("mismatch")}
        >
          <ThumbsDown aria-hidden size={16} />
        </Button>
        {chosen && (
          <Input
            aria-label="Verdict note"
            className="h-8 min-w-48 flex-1"
            maxLength={1000}
            autoFocus={pending !== null}
            value={text}
            placeholder={chosen === "mismatch" ? "What doesn't match?" : "Add a note (optional)"}
            onChange={(event) => {
              setNote(event.target.value);
              setMissingNote(false);
            }}
            onBlur={() => !pending && saveNote()}
            onKeyDown={(event) => {
              if (event.key === "Enter") saveNote();
            }}
          />
        )}
        {pending && (
          <Button type="button" size="sm" onClick={saveNote}>
            Save
          </Button>
        )}
        {!pending && saved?.status && (
          <span className="text-sm text-muted-foreground">{saved.status}</span>
        )}
        {!pending && saved?.status === "open" && (
          <>
            <Button type="button" size="sm" variant="ghost" onClick={() => close.mutate("resolved")}>
              Mark resolved
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => close.mutate("dismissed")}>
              Dismiss
            </Button>
          </>
        )}
      </div>
      {missingNote && (
        <p role="alert" className="text-sm text-destructive">
          Write what doesn't match before saving.
        </p>
      )}
      <FieldError message={failure instanceof ApiError || failure instanceof Error ? failure.message : null} />
    </section>
  );
}
