import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Circle, Pencil } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  api,
  type ChatMessage,
  type Pending,
  type Progress,
  type ResumeBody,
  type ThreadDetail,
  type ToolToggle,
  type TurnEvent,
  type Upload,
} from "../lib/api";
import { FieldError } from "../lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cardClass } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Page } from "@/components/Page";
import { Attachment } from "@/components/chat/Attachment";
import { Bubble } from "@/components/chat/Bubble";
import { Composer } from "@/components/chat/Composer";
import { QuestionForm } from "@/components/chat/QuestionForm";
import { Rail } from "@/components/chat/Rail";
import { Reply } from "@/components/chat/Reply";
import { ROLE_LABELS } from "@/components/chat/roles";
import { WaitingBubble } from "@/components/chat/WaitingBubble";

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

  const queryClient = useQueryClient();
  const change = useMutation({
    mutationFn: ({ approve, version }: { approve: boolean; version: number }) => {
      const id = progress.data?.package_id ?? "";
      return approve ? api.approveVersion(id, version) : api.unapproveVersion(id, version);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["progress", threadId] });
      queryClient.invalidateQueries({ queryKey: ["version"] });
    },
  });

  if (progress.error) return <FieldError message={message(progress.error)} />;
  if (!progress.data) return <p>Loading project…</p>;
  const p: Progress = progress.data;
  // A render replaces the blockout screenshot once there is one.
  const picture = p.still ?? p.screenshot;
  const canApproveLatest =
    p.latest_version !== null && p.build_status === "succeeded" && p.approved_version !== p.latest_version;

  return (
    <section className="space-y-3" aria-label="Project">
      {p.package_id ? (
        <p>
          <strong>{p.name}</strong> <Badge variant="secondary">{p.package_id}</Badge>{" "}
          {p.latest_version !== null && <span>version {p.latest_version}</span>}
          {p.build_status && <Badge variant="outline" className="ml-2">{p.build_status}</Badge>}
        </p>
      ) : (
        <p className="text-muted-foreground">No piece yet.</p>
      )}
      {p.package_id && p.latest_version !== null && (
        <div className="space-y-2" role="group" aria-label="Approval">
          <p>
            {p.approved_version !== null ? (
              <>
                <Badge>Approved</Badge> version {p.approved_version}
              </>
            ) : (
              <span className="text-muted-foreground">No version approved yet.</span>
            )}
          </p>
          <div className="flex flex-wrap gap-2">
            {canApproveLatest && p.latest_version !== null && (
              <Button
                type="button"
                size="sm"
                disabled={change.isPending}
                onClick={() => change.mutate({ approve: true, version: p.latest_version as number })}
              >
                Approve version {p.latest_version}
              </Button>
            )}
            {p.approved_version !== null && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={change.isPending}
                onClick={() => change.mutate({ approve: false, version: p.approved_version as number })}
              >
                Unapprove version {p.approved_version}
              </Button>
            )}
          </div>
          <FieldError message={message(change.error)} />
        </div>
      )}
      {picture && <img src={picture} alt={`Latest picture of ${p.package_id}`} className="max-h-56 rounded-md border" />}
      {p.viewer && (
        <p>
          <a href={p.viewer} target="_blank" rel="noreferrer" className="underline">
            Open the turntable viewer
          </a>
        </p>
      )}
      {p.package_id && p.latest_version !== null && p.build_status === "succeeded" && (
        <p>
          <Link to={`/pieces/${encodeURIComponent(p.package_id)}/versions/${p.latest_version}`} className="underline">
            Inspect version {p.latest_version}
          </Link>
        </p>
      )}
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

function ConfirmationCard({ pending, disabled, onAnswer }: {
  pending: Pending;
  disabled: boolean;
  onAnswer: (answer: ResumeBody) => void;
}) {
  const [reason, setReason] = useState("");
  const answer = (value: "yes" | "no") => onAnswer(reason.trim() ? { answer: value, reason: reason.trim() } : { answer: value });
  return (
    <section className={`${cardClass} mx-auto w-full max-w-xl`} aria-label="Confirmation needed">
      <h3>Confirm: {pending.subject}</h3>
      <pre className="whitespace-pre-wrap font-chat">{pending.summary}</pre>
      <Input aria-label="Reason (optional)" placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
      <div className="flex gap-2">
        <Button type="button" disabled={disabled} onClick={() => answer("yes")}>Yes</Button>
        <Button type="button" variant="outline" disabled={disabled} onClick={() => answer("no")}>No</Button>
      </div>
    </section>
  );
}

/** An answered question set: one row per question. */
function AnswersTable({ rows }: { rows: { question: string; answer: string }[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Question</TableHead>
          <TableHead>Answer</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, index) => (
          <TableRow key={index}>
            <TableCell>{row.question}</TableCell>
            <TableCell>{row.answer}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** The heading, editable in place; an empty title is refused in words. */
function Title({ threadId, title }: { threadId: string; title: string }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const rename = useMutation({
    mutationFn: (value: string) => api.renameThread(threadId, value),
    onSuccess: (thread) => {
      queryClient.setQueryData<ThreadDetail>(["thread", threadId], (old) => (old ? { ...old, title: thread.title } : old));
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      setEditing(null);
    },
  });

  if (editing === null) {
    return (
      <div className="flex items-center gap-2">
        <h1>{title || "Untitled"}</h1>
        <Button type="button" variant="ghost" size="sm" aria-label="Rename" onClick={() => setEditing(title)}>
          <Pencil aria-hidden size={16} />
        </Button>
      </div>
    );
  }
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (!editing.trim()) {
          setRefused("A conversation needs a title.");
          return;
        }
        setRefused(null);
        rename.mutate(editing.trim());
      }}
    >
      <Input aria-label="Conversation title" value={editing} maxLength={200} onChange={(e) => setEditing(e.target.value)} className="max-w-md" />
      <Button type="submit" disabled={rename.isPending}>Save</Button>
      <Button type="button" variant="outline" onClick={() => { setEditing(null); setRefused(null); }}>Cancel</Button>
      <FieldError message={refused ?? message(rename.error)} />
    </form>
  );
}

function OwnerMessage({ m, uploadById }: { m: ChatMessage; uploadById: Map<string, Upload> }) {
  const files = (m.upload_ids ?? []).map((id) => uploadById.get(id)).filter((u): u is Upload => Boolean(u));
  return (
    <Bubble side="right" speaker="You">
      <p className="font-chat text-base leading-relaxed whitespace-pre-wrap">{m.text}</p>
      {files.length > 0 && (
        <span className="mt-2 flex flex-wrap gap-2">
          {files.map((u) => <Attachment key={u.upload_id} upload={u} />)}
        </span>
      )}
    </Bubble>
  );
}

type Running = { working: string | null; tool: string | null };

export default function Conversation() {
  const { threadId = "" } = useParams();
  const queryClient = useQueryClient();
  const [specialists, setSpecialists] = useState<string[]>([]);
  const [running, setRunning] = useState<Running | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [optimistic, setOptimistic] = useState<{ text: string; uploads: Upload[] } | null>(null);
  const [panel, setPanel] = useState<string | null>(null);
  const thread = useQuery({ queryKey: ["thread", threadId], queryFn: () => api.thread(threadId) });
  const sentFiles = Boolean(thread.data?.messages.some((m) => m.upload_ids?.length));
  const uploads = useQuery({ queryKey: ["uploads", threadId], queryFn: () => api.uploads(threadId), enabled: sentFiles });
  const uploadById = new Map((uploads.data ?? []).map((u) => [u.upload_id, u]));

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["thread", threadId] }),
      queryClient.invalidateQueries({ queryKey: ["progress", threadId] }),
      queryClient.invalidateQueries({ queryKey: ["uploads", threadId] }),
      queryClient.invalidateQueries({ queryKey: ["threads"] }),
    ]);
  }

  /** Follow one turn's events; resolves to its refusal in words, or `null`. */
  async function follow(run: (onEvent: (event: TurnEvent) => void) => Promise<void>): Promise<string | null> {
    setRunning({ working: null, tool: null });
    setSpecialists([]);
    let refused: string | null = null;
    try {
      await run((event) => {
        if (event.event === "specialist") setRunning({ working: event.data.role, tool: null });
        else if (event.event === "tool") setRunning((now) => ({ working: now?.working ?? null, tool: event.data.plugin }));
        else if (event.event === "reply" || event.event === "pending") setSpecialists(event.data.specialists);
        else if (event.event === "title") {
          queryClient.setQueryData<ThreadDetail>(["thread", threadId], (old) => (old ? { ...old, title: event.data.title } : old));
        } else if (event.event === "error") refused = event.data.reason;
      });
    } catch (error) {
      refused = message(error) ?? "the turn failed";
    }
    await refresh();
    setRunning(null);
    return refused;
  }

  async function send(text: string, files: Upload[]): Promise<string | null> {
    setOptimistic({ text, uploads: files });
    const refused = await follow((onEvent) => api.streamTurn(threadId, text, files.map((u) => u.upload_id), onEvent));
    setOptimistic(null);
    return refused;
  }

  async function answer(pending: Pending, value: ResumeBody) {
    setAnswerError(null);
    setAnswerError(await follow((onEvent) => api.streamResume(threadId, pending.confirmation_id, value, onEvent)));
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
  const lastReply = messages.reduce((found, m, index) => (m.role === "assistant" && m.kind !== "answers" ? index : found), -1);

  return (
    <Page>
      <p><Link to="/conversations" className="underline">All conversations</Link></p>
      <Title key={thread.data.title} threadId={threadId} title={thread.data.title} />
      <div className="relative flex gap-2">
        <Rail
          open={panel}
          onOpen={setPanel}
          panels={[
            { id: "tools", label: "Tools", icon: "tools", content: <Tools threadId={threadId} /> },
            { id: "project", label: "Project", icon: "project", content: <ProjectPanel threadId={threadId} /> },
          ]}
        />
        <div className="min-w-0 flex-1 space-y-4">
          <section className={`${cardClass} space-y-4`} aria-label="Messages">
            {messages.length === 0 && !optimistic && <p className="text-muted-foreground">Nothing said yet. Describe the piece you want.</p>}
            {messages.map((m, index) => {
              if (m.role === "confirmation") {
                return (
                  <p key={index} className="mx-auto w-fit rounded-md border px-3 py-2 text-sm text-muted-foreground" data-role="confirmation">
                    Answered: {m.text}
                  </p>
                );
              }
              if (m.kind === "answers") {
                return (
                  <div key={index} className="mx-auto w-full max-w-xl" data-role="answers">
                    <AnswersTable rows={m.rows ?? []} />
                  </div>
                );
              }
              if (m.role === "owner") return <OwnerMessage key={index} m={m} uploadById={uploadById} />;
              return (
                <Bubble key={index} side="left" speaker="Foreman">
                  <Reply text={m.text} />
                  {index === lastReply && specialists.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1" aria-label="Specialists in this turn">
                      {specialists.map((role) => (
                        <Badge key={role} variant="outline">{ROLE_LABELS[role] ?? role}</Badge>
                      ))}
                    </div>
                  )}
                </Bubble>
              );
            })}
            {optimistic && (
              <OwnerMessage m={{ role: "owner", text: optimistic.text, upload_ids: optimistic.uploads.map((u) => u.upload_id) }} uploadById={new Map(optimistic.uploads.map((u) => [u.upload_id, u]))} />
            )}
            {running && <WaitingBubble working={running.working} tool={running.tool} />}
          </section>
          {pending ? (
            <>
              {pending.kind === "questions" ? (
                <QuestionForm
                  key={pending.confirmation_id}
                  questions={pending.questions ?? []}
                  disabled={running !== null}
                  onAnswer={(value) => void answer(pending, value)}
                />
              ) : (
                <ConfirmationCard
                  key={pending.confirmation_id}
                  pending={pending}
                  disabled={running !== null}
                  onAnswer={(value) => void answer(pending, value)}
                />
              )}
              <FieldError message={answerError} />
            </>
          ) : (
            <Composer threadId={threadId} running={running !== null} onSend={send} />
          )}
        </div>
      </div>
    </Page>
  );
}
