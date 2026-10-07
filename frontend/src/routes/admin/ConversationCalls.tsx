import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../lib/api";
import { FieldError } from "../../lib/form";
import { Label } from "@/components/ui/label";
import { Page } from "@/components/Page";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { ROLE_LABELS } from "@/components/chat/roles";

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

  return (
    <Page>
      <h1>Conversation calls</h1>
      {threads.data?.length === 0 && <p>No conversations yet.</p>}
      {threads.data && threads.data.length > 0 && (
        <Label className="flex flex-wrap items-center gap-2">
          Conversation
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={threadId}
            onChange={(event) => setChosen(event.target.value)}
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
            </TableRow>
          </TableHeader>
          <TableBody>
            {calls.data.map((call, index) => (
              <TableRow key={`${call.time}-${index}`}>
                <TableCell><time dateTime={call.time}>{new Date(call.time).toLocaleString()}</time></TableCell>
                <TableCell>{ROLE_LABELS[call.slot] ?? call.slot}</TableCell>
                <TableCell>{call.operation}</TableCell>
                <TableCell>{call.model}</TableCell>
                <TableCell>
                  {call.input_tokens ?? "—"}
                  {call.estimated && <span className="text-muted-foreground"> (estimate)</span>}
                </TableCell>
                <TableCell>{call.output_tokens ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Page>
  );
}
