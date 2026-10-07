import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Circle } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Pending, type Progress, type ToolToggle, type Upload } from "../lib/api";
import { FieldError } from "../lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";

const STEP_LABELS: Record<string, string> = {
  brief: "Brief confirmed",
  piece: "Piece created",
  built: "Built",
  rendered: "Rendered",
  reviewed: "Reviewed",
  detail: "Detail pass",
  final: "Final render",
};

function message(error: unknown): string | null {
  return error instanceof Error ? error.message : null;
}

function Tools({ threadId }: { threadId: string }) {
  const queryClient = useQueryClient();
  const tools = useQuery({ queryKey: ["tools", threadId], queryFn: () => api.tools(threadId) });
  const toggle = useMutation({
    mutationFn: ({ plugin, enabled }: { plugin: string; enabled: boolean }) => api.setTool(threadId, plugin, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tools", threadId] }),
  });

  if (tools.isLoading) return <p>Loading tools…</p>;
  if (!tools.data) return null;

  return (
    <ul>
      {tools.data.map((tool: ToolToggle) => (
        <li key={tool.plugin} className="flex items-center justify-between gap-4">
          <div>
            <strong>{tool.plugin.replaceAll("_", " ")}</strong>
            <div>{tool.description}</div>
            {!tool.toggleable && <small className="text-muted-foreground">Always on</small>}
          </div>
          <Label>
            <Input
              type="checkbox"
              checked={tool.enabled}
              disabled={!tool.toggleable}
              aria-label={tool.plugin}
              onChange={(event) => toggle.mutate({ plugin: tool.plugin, enabled: event.target.checked })}
            />
          </Label>
        </li>
      ))}
    </ul>
  );
}

function ProjectPanel({ threadId }: { threadId: string }) {
  const progress = useQuery({
    queryKey: ["progress", threadId],
    queryFn: () => api.progress(threadId),
    refetchInterval: (query) => {
      const status = query.state.data?.build_status;
      return status === "queued" || status === "running" ? 3000 : false;
    },
  });

  if (progress.error) return <FieldError message={message(progress.error)} />;
  if (!progress.data) return <p>Loading project…</p>;
  const p: Progress = progress.data;
  const picture = p.screenshot ?? p.still;

  return (
    <section className={cardClass} aria-label="Project">
      <h2>Project</h2>
      {p.package_id ? (
        <p>
          <strong>{p.name}</strong> <Badge variant="secondary">{p.package_id}</Badge>{" "}
          {p.latest_version !== null && <span>version {p.latest_version}</span>}
          {p.build_status && <Badge variant="outline" className="ml-2">{p.build_status}</Badge>}
        </p>
      ) : (
        <p className="text-muted-foreground">No piece yet.</p>
      )}
      {picture && <img src={picture} alt={`Latest picture of ${p.package_id}`} className="max-h-56 rounded-md border" />}
      <ol className="space-y-1">
        {p.steps.map((step) => (
          <li key={step.step} className="flex items-center gap-2" data-done={step.done}>
            {step.done ? <Check aria-hidden size={16} /> : <Circle aria-hidden size={16} className="text-muted-foreground" />}
            <span>
              {STEP_LABELS[step.step] ?? step.step}
              {step.done && step.detail ? ` (${step.detail})` : ""}
            </span>
            <span className="sr-only">{step.done ? "done" : "not yet"}</span>
          </li>
        ))}
      </ol>
      <p>
        <strong>Next:</strong> {p.next_step}
      </p>
      {p.open_review_items > 0 && (
        <p>
          {p.open_review_items} open review {p.open_review_items === 1 ? "item" : "items"}.{" "}
          <Link to="/pieces" className="underline">Open the piece's page</Link>
        </p>
      )}
      {p.open_requests.length > 0 && (
        <div>
          <h3>Waiting on a generator extension</h3>
          <ul>
            {p.open_requests.map((r) => (
              <li key={r.field}>
                <code>{r.field}</code>: {r.request}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function ConfirmationCard({ threadId, pending, disabled, onAnswered }: {
  threadId: string;
  pending: Pending;
  disabled: boolean;
  onAnswered: (specialist: string | null) => void;
}) {
  const [reason, setReason] = useState("");
  const answer = useMutation({
    mutationFn: (value: "yes" | "no") => api.resume(threadId, pending.confirmation_id, value, reason.trim() || null),
    onSuccess: (turn) => {
      setReason("");
      onAnswered(turn.specialist);
    },
  });
  return (
    <section className={cardClass} aria-label="Confirmation needed">
      <h3>Confirm: {pending.subject}</h3>
      <pre className="whitespace-pre-wrap font-sans">{pending.summary}</pre>
      <Input aria-label="Reason (optional)" placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
      <div className="flex gap-2">
        <Button type="button" disabled={disabled || answer.isPending} onClick={() => answer.mutate("yes")}>Yes</Button>
        <Button type="button" variant="outline" disabled={disabled || answer.isPending} onClick={() => answer.mutate("no")}>No</Button>
      </div>
      <FieldError message={message(answer.error)} />
    </section>
  );
}

function Composer({ threadId, onStart, onDone, onFailed }: {
  threadId: string;
  onStart: (text: string, uploads: Upload[]) => void;
  onDone: (specialist: string | null) => Promise<void>;
  onFailed: () => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const files = useRef<HTMLInputElement>(null);

  const send = useMutation({
    mutationFn: ({ body, ids }: { body: string; ids: string[]; sent: Upload[] }) => api.sendTurn(threadId, body, ids),
    onSuccess: (turn) => onDone(turn.specialist),
    onError: (_error, vars) => {
      // The unanswered message is not kept: give the owner their words back.
      setText(vars.body);
      setUploads(vars.sent);
      return onFailed();
    },
  });

  async function attach(list: FileList | null) {
    setUploadError(null);
    for (const file of Array.from(list ?? [])) {
      try {
        const added = await api.upload(threadId, file);
        setUploads((current) => [...current, added]);
      } catch (error) {
        setUploadError(message(error));
      }
    }
    if (files.current) files.current.value = "";
  }

  function submit() {
    const body = text.trim();
    if (!body) return;
    onStart(body, uploads);
    send.mutate({ body, ids: uploads.map((u) => u.upload_id), sent: uploads });
    setText("");
    setUploads([]);
  }

  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      {uploads.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {uploads.map((u) => (
            <img key={u.upload_id} src={`/uploads/${u.upload_id}`} alt={u.original_name} className="h-16 rounded-md border" />
          ))}
        </div>
      )}
      <Input
        aria-label="Message"
        value={text}
        placeholder="Describe what you want…"
        disabled={send.isPending}
        onChange={(event) => setText(event.target.value)}
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={send.isPending || !text.trim()}>Send</Button>
        <Label className="cursor-pointer text-sm underline">
          Add a plan or photo
          <input
            ref={files}
            type="file"
            accept="image/png,image/jpeg"
            multiple
            className="sr-only"
            aria-label="Add a plan or photo"
            disabled={send.isPending}
            onChange={(event) => void attach(event.target.files)}
          />
        </Label>
        {send.isPending && <span role="status">Waiting for the reply…</span>}
      </div>
      <FieldError message={uploadError ?? message(send.error)} />
    </form>
  );
}

export default function Conversation() {
  const { threadId = "" } = useParams();
  const queryClient = useQueryClient();
  const [specialist, setSpecialist] = useState<string | null>(null);
  const [optimistic, setOptimistic] = useState<{ text: string; uploads: Upload[] } | null>(null);
  const thread = useQuery({ queryKey: ["thread", threadId], queryFn: () => api.thread(threadId) });

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["thread", threadId] }),
      queryClient.invalidateQueries({ queryKey: ["progress", threadId] }),
      queryClient.invalidateQueries({ queryKey: ["threads"] }),
    ]);
  }

  if (thread.error) {
    return (
      <Page>
        <FieldError message={message(thread.error)} />
        <Link to="/conversations" className="underline">All conversations</Link>
      </Page>
    );
  }
  if (!thread.data) return <Page>Loading…</Page>;
  const { messages, pending } = thread.data;

  return (
    <Page>
      <p><Link to="/conversations" className="underline">All conversations</Link></p>
      <h1>{thread.data.title || "Untitled"}</h1>
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          <section className={cardClass} aria-label="Messages">
            {messages.length === 0 && !optimistic && <p className="text-muted-foreground">Nothing said yet. Describe the piece you want.</p>}
            {messages.map((m, index) => (
              <p key={index} className={m.role === "owner" ? "font-medium" : ""}>
                <strong>{m.role === "owner" ? "You" : "Foreman"}:</strong> {m.text}
                {m.role === "assistant" && index === messages.length - 1 && specialist && (
                  <Badge variant="outline" className="ml-2">{specialist}</Badge>
                )}
              </p>
            ))}
            {optimistic && (
              <div>
                <p className="font-medium"><strong>You:</strong> {optimistic.text}</p>
                {optimistic.uploads.map((u) => (
                  <img key={u.upload_id} src={`/uploads/${u.upload_id}`} alt={u.original_name} className="mt-1 h-16 rounded-md border" />
                ))}
              </div>
            )}
          </section>
          {pending ? (
            <ConfirmationCard
              key={pending.confirmation_id}
              threadId={threadId}
              pending={pending}
              disabled={false}
              onAnswered={(who) => {
                setSpecialist(who);
                void refresh();
              }}
            />
          ) : (
            <Composer
              threadId={threadId}
              onStart={(text, uploads) => setOptimistic({ text, uploads })}
              onDone={async (who) => {
                setSpecialist(who);
                await refresh();
                setOptimistic(null);
              }}
              onFailed={async () => {
                setOptimistic(null);
                await refresh();
              }}
            />
          )}
        </div>
        <div className="space-y-4">
          <ProjectPanel threadId={threadId} />
          <section className={cardClass} aria-label="Tools">
            <h2>Tools</h2>
            <Tools threadId={threadId} />
          </section>
        </div>
      </div>
    </Page>
  );
}
