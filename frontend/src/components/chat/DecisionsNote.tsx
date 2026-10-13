import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../lib/api";
import { Button } from "@/components/ui/button";

// `line` is the row's line in the note, `bullet` its marker, `labelled` whether it carries its own "**Topic:**".
type Row = { topic: string; decision: string; line: number; bullet: string; labelled: boolean };

/** The note's bullets as table rows: a "**Label:**" opens its own topic, otherwise the last heading is the topic.
 * A "Decisions so far" title line is dropped (the panel already carries it). */
export function noteRows(text: string): Row[] {
  const rows: Row[] = [];
  let topic = "";
  for (const [number, raw] of text.split("\n").entries()) {
    const line = raw.trim();
    if (!line) continue;
    const heading = line.match(/^#+\s*(.*?)\s*:?$/) ?? line.match(/^\*\*(.*?):?\*\*:?$/);
    if (heading) {
      if (!/^decisions so far$/i.test(heading[1])) topic = heading[1];
      continue;
    }
    const bullet = line.match(/^([-*•]|\d+[.)])\s+/)?.[1] ?? "-";
    const item = line.replace(/^([-*•]|\d+[.)])\s+/, "");
    // "**Room:** text" names its own topic; other lines sit under the last heading.
    const label = item.match(/^\*\*(.+?):?\*\*:?\s*(.*)$/);
    const row = label ? { topic: label[1], decision: label[2] } : { topic, decision: item };
    rows.push({ ...row, decision: row.decision.replace(/\*\*/g, ""), line: number, bullet, labelled: !!label });
  }
  return rows;
}

/** The note with one row's line rewritten. A changed topic (or an already labelled row) is written as
 * "**Topic:** decision"; an unchanged topic under a heading stays a plain bullet. */
export function replaceRow(text: string, row: Row, topic: string, decision: string): string {
  const one = (value: string) => value.replace(/\s+/g, " ").trim();
  const [newTopic, newDecision] = [one(topic), one(decision)];
  const lines = text.split("\n");
  lines[row.line] =
    row.labelled || newTopic !== row.topic
      ? `${row.bullet} **${newTopic}:** ${newDecision}`
      : `${row.bullet} ${newDecision}`;
  return lines.join("\n");
}

/** The note with a new "- **Topic:** decision" line at the end. */
export function appendRow(text: string, topic: string, decision: string): string {
  const one = (value: string) => value.replace(/\s+/g, " ").trim();
  const line = `- **${one(topic)}:** ${one(decision)}`;
  return text.trim() ? `${text.trimEnd()}\n${line}` : line;
}

/** The note without one row's line. A heading left with no bullets under it goes too. */
export function deleteRow(text: string, row: Row): string {
  const lines = text.split("\n").filter((_, number) => number !== row.line);
  const isHeading = (line: string) => /^#+\s/.test(line.trim());
  return lines
    .filter((line, number) => {
      if (!isHeading(line)) return true;
      const next = lines.slice(number + 1).find((other) => other.trim());
      return next !== undefined && !isHeading(next);
    })
    .join("\n")
    .trim();
}

const ROWS_PER_PAGE = 5;

/** The page's rows (five at a time, in the note's order) and the page count. */
export function pageOfRows(rows: Row[], page: number): { rows: Row[]; pages: number } {
  const pages = Math.max(1, Math.ceil(rows.length / ROWS_PER_PAGE));
  const start = Math.min(Math.max(page, 0), pages - 1) * ROWS_PER_PAGE;
  return { rows: rows.slice(start, start + ROWS_PER_PAGE), pages };
}

/** The conversation's "decisions so far" note: read it, correct it, or compress now
 * (conversation-memory-settings). Never shows tokens, budgets or models. */
export function DecisionsNote({
  threadId,
  prefill,
  onPrefillUsed,
}: {
  threadId: string;
  /** A chat message's text offered as a new row ("Add to decisions"); the owner gives the topic and saves. */
  prefill?: string;
  /** Called once the new row is saved or cancelled, so the offer is not made again. */
  onPrefillUsed?: () => void;
}) {
  const queryClient = useQueryClient();
  const key = ["conversation-note", threadId];
  const note = useQuery({ queryKey: key, queryFn: () => api.conversationNote(threadId) });
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(prefill === undefined ? 0 : Number.MAX_SAFE_INTEGER);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [adding, setAdding] = useState<{ topic: string; decision: string } | null>(
    prefill === undefined ? null : { topic: "", decision: prefill.slice(0, 2000) },
  );
  const [editing, setEditing] = useState<{ line: number; topic: string; decision: string } | null>(null);
  const done = (value: Awaited<ReturnType<typeof api.conversationNote>>) => {
    setError(null);
    setEditing(null);
    setAdding(null);
    setDeleting(null);
    onPrefillUsed?.();
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
  const rows = text ? noteRows(text) : [];
  const paged = pageOfRows(rows, page);
  const current = Math.min(page, paged.pages - 1);
  return (
    <section className="space-y-3" aria-label="Decisions so far">
      <p className="text-sm text-muted-foreground">
        {note.data.package_id ? `For ${note.data.package_id}. ` : ""}
        Earlier parts of a long conversation are sent to the assistants as this note. The full conversation stays
        here.
      </p>
      <>
          {text || adding ? (
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-1 pr-3 font-medium">Topic</th>
                  <th className="py-1 pr-3 font-medium">Decision</th>
                  <th className="py-1 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {paged.rows.map((row) =>
                  editing?.line === row.line ? (
                    <tr key={row.line} className="border-b align-top">
                      <td className="py-1 pr-3">
                        <input
                          aria-label="Topic"
                          className="w-full rounded-md border px-2 py-1 text-sm"
                          maxLength={200}
                          value={editing.topic}
                          onChange={(event) => setEditing({ ...editing, topic: event.target.value })}
                        />
                      </td>
                      <td className="py-1 pr-3">
                        <textarea
                          aria-label="Decision"
                          className="w-full rounded-md border px-2 py-1 text-sm"
                          rows={3}
                          maxLength={2000}
                          value={editing.decision}
                          onChange={(event) => setEditing({ ...editing, decision: event.target.value })}
                        />
                      </td>
                      <td className="flex gap-1 py-1">
                        <Button
                          type="button"
                          size="sm"
                          disabled={save.isPending || !editing.decision.trim() || !editing.topic.trim()}
                          onClick={() => save.mutate(replaceRow(text ?? "", row, editing.topic, editing.decision))}
                        >
                          Save
                        </Button>
                        <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(null)}>
                          Cancel
                        </Button>
                      </td>
                    </tr>
                  ) : (
                    <tr key={row.line} className="border-b align-top">
                      <td className="py-1 pr-3 text-muted-foreground">{row.topic}</td>
                      <td className="py-1 pr-3">{row.decision}</td>
                      <td className="flex gap-1 py-1">
                        {deleting === row.line ? (
                          <>
                            <Button
                              type="button"
                              variant="destructive"
                              size="sm"
                              aria-label={`Confirm delete ${row.topic || "row"}`}
                              disabled={save.isPending}
                              onClick={() => save.mutate(deleteRow(text ?? "", row))}
                            >
                              Delete?
                            </Button>
                            <Button type="button" variant="ghost" size="sm" onClick={() => setDeleting(null)}>
                              Keep
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              aria-label={`Edit ${row.topic || "row"}`}
                              onClick={() => {
                                setAdding(null);
                                setDeleting(null);
                                setEditing({ line: row.line, topic: row.topic, decision: row.decision });
                              }}
                            >
                              Edit
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              aria-label={`Delete ${row.topic || "row"}`}
                              disabled={rows.length < 2}
                              title={rows.length < 2 ? "The note needs at least one row" : undefined}
                              onClick={() => {
                                setAdding(null);
                                setEditing(null);
                                setDeleting(row.line);
                              }}
                            >
                              Delete
                            </Button>
                          </>
                        )}
                      </td>
                    </tr>
                  ),
                )}
                {adding && current === paged.pages - 1 && (
                  <tr className="border-b align-top">
                    <td className="py-1 pr-3">
                      <input
                        aria-label="New topic"
                        className="w-full rounded-md border px-2 py-1 text-sm"
                        maxLength={200}
                        value={adding.topic}
                        onChange={(event) => setAdding({ ...adding, topic: event.target.value })}
                      />
                    </td>
                    <td className="py-1 pr-3">
                      <textarea
                        aria-label="New decision"
                        className="w-full rounded-md border px-2 py-1 text-sm"
                        rows={3}
                        maxLength={2000}
                        value={adding.decision}
                        onChange={(event) => setAdding({ ...adding, decision: event.target.value })}
                      />
                    </td>
                    <td className="flex gap-1 py-1">
                      <Button
                        type="button"
                        size="sm"
                        disabled={save.isPending || !adding.decision.trim() || !adding.topic.trim()}
                        onClick={() => save.mutate(appendRow(text ?? "", adding.topic, adding.decision))}
                      >
                        Save
                      </Button>
                      <Button type="button" variant="ghost" size="sm" onClick={() => {
                          setAdding(null);
                          onPrefillUsed?.();
                        }}>
                        Cancel
                      </Button>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-muted-foreground">There is no note yet.</p>
          )}
          {paged.pages > 1 && (
            <div className="flex items-center gap-2 text-sm">
              <Button type="button" variant="outline" size="sm" disabled={current === 0} onClick={() => setPage(current - 1)}>
                Previous
              </Button>
              <span>
                Page {current + 1} of {paged.pages}
              </span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={current === paged.pages - 1}
                onClick={() => setPage(current + 1)}
              >
                Next
              </Button>
            </div>
          )}
          {note.data.owner_edited && <p className="text-xs text-muted-foreground">Corrected by you.</p>}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!!adding}
              onClick={() => {
                setEditing(null);
                setAdding({ topic: "", decision: "" });
                setPage(Number.MAX_SAFE_INTEGER);
              }}
            >
              Add Topic Decision
            </Button>
            <Button type="button" size="sm" disabled={compress.isPending} onClick={() => compress.mutate()}>
              {compress.isPending ? "Compressing…" : "Compress now"}
            </Button>
          </div>
      </>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </section>
  );
}
