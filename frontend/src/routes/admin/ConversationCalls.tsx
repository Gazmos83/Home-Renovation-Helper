import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../lib/api";
import { FieldError } from "../../lib/form";
import { Label } from "@/components/ui/label";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { ROLE_LABELS } from "@/components/chat/roles";
import { UsageCharts } from "@/components/UsageCharts";

const pageSize = 20;

/** One conversation's model calls, newest first (dev-panel; studio-chat-polish). */
export default function ConversationCalls() {
  const threads = useQuery({ queryKey: ["threads"], queryFn: api.threads });
  const [chosen, setChosen] = useState("");
  const threadId = chosen || threads.data?.[0]?.thread_id || "";
  const calls = useQuery({
    queryKey: ["admin-thread-calls", threadId],
    queryFn: () => api.threadCalls(threadId),
    enabled: Boolean(threadId),
  });
  const [page, setPage] = useState(0);
  const listed = calls.data ?? [];
  const pages = Math.max(1, Math.ceil(listed.length / pageSize));
  const current = Math.min(page, pages - 1);
  const shown = listed.slice(current * pageSize, (current + 1) * pageSize);

  return (
    <>
      <UsageCharts />
      <h2>Conversation calls</h2>
      {threads.data?.length === 0 && <p>No conversations yet.</p>}
      {threads.data && threads.data.length > 0 && (
        <Label className="flex flex-wrap items-center gap-2">
          Conversation
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={threadId}
            onChange={(event) => {
              setChosen(event.target.value);
              setPage(0);
            }}
          >
            {threads.data.map((t) => (
              <option key={t.thread_id} value={t.thread_id}>
                {t.title || "Untitled"} · {new Date(t.last_turn_at).toLocaleString()}
              </option>
            ))}
          </select>
        </Label>
      )}
      <FieldError message={calls.error instanceof Error ? calls.error.message : null} />
      {calls.data && calls.data.length === 0 && <p>No model calls recorded for this conversation.</p>}
      {calls.data && calls.data.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Specialist</TableHead>
              <TableHead>Call</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Input</TableHead>
              <TableHead>Output</TableHead>
              <TableHead>Trace</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.map((call, index) => (
              <TableRow key={`${call.time}-${current * pageSize + index}`}>
                <TableCell><time dateTime={call.time}>{new Date(call.time).toLocaleString()}</time></TableCell>
                <TableCell>{ROLE_LABELS[call.slot] ?? call.slot}</TableCell>
                <TableCell>{call.operation}</TableCell>
                <TableCell>{call.model}</TableCell>
                <TableCell>
                  {call.input_tokens ?? "—"}
                  {call.estimated && <span className="text-muted-foreground"> (estimate)</span>}
                </TableCell>
                <TableCell>{call.output_tokens ?? "—"}</TableCell>
                <TableCell>
                  {call.trace_url ? (
                    <a href={call.trace_url} target="_blank" rel="noreferrer" className="underline">
                      Langfuse
                    </a>
                  ) : (
                    "—"
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {calls.data && pages > 1 && (
        <nav aria-label="Call pages" className="flex items-center justify-between gap-3">
          <Button variant="outline" size="sm" disabled={current === 0} onClick={() => setPage(current - 1)}>
            Previous page
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {current + 1} of {pages} ({listed.length} calls)
          </span>
          <Button variant="outline" size="sm" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
            Next page
          </Button>
        </nav>
      )}
    </>
  );
}
