import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { Check, Circle, Pencil, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
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
import { Notice } from "@/components/chat/Notice";
import { Composer } from "@/components/chat/Composer";
import { QuestionForm } from "@/components/chat/QuestionForm";
import { Rail } from "@/components/chat/Rail";
import { Reply } from "@/components/chat/Reply";
import { ROLE_LABELS } from "@/components/chat/roles";
import { WaitingBubble } from "@/components/chat/WaitingBubble";
import { InspectorView } from "@/components/inspector/InspectorView";
import { RoomView, VersionSelect } from "@/components/inspector/RoomView";
import { DecisionsNote } from "@/components/chat/DecisionsNote";
import { DeleteCompositionVersion } from "@/components/DeleteCompositionVersion";
import { DeleteVersion } from "@/components/DeleteVersion";

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

/** The conversation's room or apartment, with its 3D view or why there is none (project-room-inspection). */
function RoomSection({
  room,
  threadId,
  onInspectRoom,
}: {
  room: NonNullable<Progress["room"]>;
  threadId: string;
  onInspectRoom: (slug: string) => void;
}) {
  const queryClient = useQueryClient();
  const what = room.scope === "apartment" ? "the apartment" : "the room";
  const latest = room.versions?.[0] ?? null;
  const approved = room.approved_version ?? null;
  const canApproveLatest =
    room.slug !== null && latest !== null && latest.status === "succeeded" && approved !== latest.version;
  const reload = () => {
    queryClient.invalidateQueries({ queryKey: ["progress", threadId] });
    queryClient.invalidateQueries({ queryKey: ["compositions"] });
  };
  const change = useMutation({
    mutationFn: (approve: boolean) => {
      const slug = room.slug as string;
      const version = approve ? (latest as { version: number }).version : (approved as number);
      return approve
        ? api.approveCompositionVersion(slug, version)
        : api.unapproveCompositionVersion(slug, version);
    },
    onSuccess: reload,
  });
  return (
    <div className="space-y-2" role="group" aria-label="Room">
      <h3>Selected room</h3>
      <p>
        <strong>{room.name}</strong>
      </p>
      {room.slug && latest && (
        <div className="space-y-2" role="group" aria-label={`Approval of ${room.name}`}>
          <p>
            Latest version {latest.version}.{" "}
            {approved !== null ? (
              <>
                <Badge>Approved</Badge> version {approved}
              </>
            ) : (
              <span className="text-muted-foreground">No version approved yet.</span>
            )}
          </p>
          <div className="flex flex-wrap gap-2">
            {canApproveLatest && (
              <Button
                type="button"
                size="sm"
                disabled={change.isPending}
                onClick={() => change.mutate(true)}
              >
                Approve version {latest.version}
              </Button>
            )}
            {approved !== null && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={change.isPending}
                onClick={() => change.mutate(false)}
              >
                Unapprove version {approved}
              </Button>
            )}
          </div>
          <FieldError message={message(change.error)} />
          {approved !== latest.version && (
            <DeleteCompositionVersion
              key={`${room.slug}/${latest.version}`}
              slug={room.slug}
              name={room.name}
              version={latest.version}
              only={(room.versions?.length ?? 1) === 1}
              onDeleted={reload}
            />
          )}
        </div>
      )}
      {room.slug && room.model && room.surfaces ? (
        <p>
          <Button type="button" variant="outline" onClick={() => onInspectRoom(room.slug as string)}>
            Inspect {room.name}
          </Button>
        </p>
      ) : room.slug ? (
        <p className="text-sm text-muted-foreground">Composing {room.name} again adds the 3D view.</p>
      ) : (
        <p className="text-sm text-muted-foreground">
          {room.name} has no 3D view yet. Ask the Designer to compose {what}.
        </p>
      )}
    </div>
  );
}

function ProjectPanel({
  threadId,
  progress,
  onInspect,
  onInspectRoom,
  onDeleted,
}: {
  threadId: string;
  progress: UseQueryResult<Progress>;
  onInspect: (packageId: string, version: number) => void;
  onInspectRoom: (slug: string) => void;
  /** A version of the piece was deleted. */
  onDeleted: (packageId: string, version: number) => void;
}) {
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
  const building = p.build_status === "queued" || p.build_status === "running";
  // The heads-up shows from three short of the limit ("13 of 15 versions").
  const nearLimit = p.package_id !== null && p.version_count > p.max_versions - 3;

  return (
    <section className="space-y-3" aria-label="Project">
      {p.package_id ? (
        <p>
          <strong>{p.name}</strong> <Badge variant="secondary">{p.package_id}</Badge>
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
      {p.package_id && p.latest_version !== null && (
        <div className="space-y-2">
          {nearLimit && (
            <p className="text-sm">
              {p.version_count} of {p.max_versions} versions
            </p>
          )}
          {/* No delete while the latest version builds (it would be refused) or once it is approved. */}
          {!building && p.approved_version !== p.latest_version && (
            <DeleteVersion
              key={`${p.package_id}/${p.latest_version}`}
              packageId={p.package_id}
              version={p.latest_version}
              only={p.version_count === 1}
              onDeleted={() => onDeleted(p.package_id as string, p.latest_version as number)}
            />
          )}
        </div>
      )}
      {picture && <img src={picture} alt={`Latest picture of ${p.package_id}`} className="max-h-56 rounded-md border" />}
      {p.package_id && p.latest_version !== null && p.build_status === "succeeded" && (
        <p>
          <Button
            type="button"
            variant="outline"
            onClick={() => onInspect(p.package_id as string, p.latest_version as number)}
          >
            Inspect version {p.latest_version}
          </Button>
        </p>
      )}
      {p.room && <RoomSection room={p.room} threadId={threadId} onInspectRoom={onInspectRoom} />}
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

function OwnerMessage({ m, uploadById, onEdit }: {
  m: ChatMessage;
  uploadById: Map<string, Upload>;
  /** Only the latest owner message, while nothing runs or waits, can be edited. */
  onEdit?: () => void;
}) {
  const files = (m.upload_ids ?? []).map((id) => uploadById.get(id)).filter((u): u is Upload => Boolean(u));
  return (
    <Bubble side="right" speaker="You">
      <p className="font-chat text-base leading-relaxed whitespace-pre-wrap">{m.text}</p>
      {files.length > 0 && (
        <span className="mt-2 flex flex-wrap gap-2">
          {files.map((u) => <Attachment key={u.upload_id} upload={u} />)}
        </span>
      )}
      {onEdit && (
        <Button type="button" variant="ghost" size="sm" className="mt-1" onClick={onEdit}>
          Edit
        </Button>
      )}
    </Bubble>
  );
}

/** The side pane beside the chat: a piece version or the conversation's room. */
const paneClass =
  "min-w-0 space-y-2 lg:sticky lg:top-[calc(var(--header-h)+1rem)] lg:max-h-(--chat-h) lg:overflow-y-auto";

/** `?room=<slug>` or `?room=<slug>/<n>`: the room shown beside the chat and its version, or `null`. */
function parseRoom(value: string | null): { slug: string; version: number | null } | null {
  const found = value?.match(/^([a-z0-9][a-z0-9-]*)(?:\/(\d+))?$/i);
  if (!found) return null;
  return { slug: found[1], version: found[2] ? Number(found[2]) : null };
}

/** `?inspect=<package-id>/<n>`: the version shown beside the chat, or `null`. */
function parseInspect(value: string | null): { packageId: string; version: number } | null {
  const found = value?.match(/^([a-z0-9][a-z0-9-]*)\/(\d+)$/i);
  if (!found || Number(found[2]) < 1) return null;
  return { packageId: found[1], version: Number(found[2]) };
}

type Running = { working: string | null; tool: string | null };

/** How close to the end of the messages box still counts as being at the last message. */
const AT_BOTTOM_PX = 32;

export default function Conversation() {
  const { threadId = "" } = useParams();
  const queryClient = useQueryClient();
  const [specialists, setSpecialists] = useState<string[]>([]);
  const [running, setRunning] = useState<Running | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [optimistic, setOptimistic] = useState<{ text: string; uploads: Upload[] } | null>(null);
  const [panel, setPanel] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ messageId: string; text: string } | null>(null);
  const [kept, setKept] = useState<string[]>([]);
  // The running turn's stream, aborted only when the stop route finds no turn to stop.
  const stream = useRef<AbortController | null>(null);
  const [params, setParams] = useSearchParams();
  const inspected = parseInspect(params.get("inspect"));

  // The progress runs here so a finished build or render is noticed with the panel closed.
  const progress = useQuery({
    queryKey: ["progress", threadId],
    queryFn: () => api.progress(threadId),
    refetchInterval: (query) => {
      const status = query.state.data?.build_status;
      return status === "queued" || status === "running" || query.state.data?.rendering ? 3000 : false;
    },
  });
  const building = ["queued", "running"].includes(progress.data?.build_status ?? "");
  // A render or a build posts its notice when it ends (version-cleanup-and-inspection).
  const following = (progress.data?.rendering ?? false) || building;
  const thread = useQuery({
    queryKey: ["thread", threadId],
    queryFn: () => api.thread(threadId),
    refetchInterval: following ? 3000 : false,
  });
  // Once a render or build ends its notice is in the thread: read it again one last time.
  const wasFollowing = useRef(false);
  useEffect(() => {
    if (wasFollowing.current && !following) queryClient.invalidateQueries({ queryKey: ["thread", threadId] });
    wasFollowing.current = following;
  }, [following, queryClient, threadId]);
  // The messages box scrolls by itself and follows new items only while the owner is at its end.
  const list = useRef<HTMLElement>(null);
  const atBottom = useRef(true);
  const column = useRef<HTMLDivElement>(null);
  const [columnTop, setColumnTop] = useState(0);
  const loaded = thread.data !== undefined;
  useLayoutEffect(() => {
    function measure() {
      if (column.current) setColumnTop(column.current.getBoundingClientRect().top + window.scrollY);
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [loaded]);
  useEffect(() => {
    atBottom.current = true;
  }, [threadId]);
  const messageCount = thread.data?.messages.length ?? 0;
  const lastLength = thread.data?.messages.at(-1)?.text.length ?? 0;
  useLayoutEffect(() => {
    if (list.current && atBottom.current) list.current.scrollTop = list.current.scrollHeight;
    // `columnTop` too: measuring the column shortens the box after its first scroll.
  }, [loaded, columnTop, messageCount, lastLength, optimistic, running?.working, running?.tool, kept.length]);
  function onScroll() {
    const box = list.current;
    if (box) atBottom.current = box.scrollHeight - box.scrollTop - box.clientHeight <= AT_BOTTOM_PX;
  }

  const inspectedSpec = useQuery({
    queryKey: ["spec", inspected?.packageId, inspected?.version],
    queryFn: () => api.pieceSpec(inspected?.packageId as string, inspected?.version as number),
    enabled: inspected !== null,
    retry: false,
  });

  function deleted(packageId: string, version: number) {
    queryClient.removeQueries({ queryKey: ["version", packageId, version] });
    queryClient.invalidateQueries({ queryKey: ["piece-versions", packageId] });
    queryClient.invalidateQueries({ queryKey: ["pieces"] });
    void refresh();
    if (inspected?.packageId === packageId && inspected.version === version) inspect(null);
  }

  // One side pane at a time: opening a piece version closes the room view (project-room-inspection).
  function inspect(packageId: string | null, version?: number) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (packageId && version) {
          next.set("inspect", `${packageId}/${version}`);
          next.delete("room");
        } else next.delete("inspect");
        return next;
      },
      { replace: true },
    );
  }

  // `?room=<slug>[/<n>]`: the conversation's room beside the chat; opening it closes the piece inspector.
  function inspectRoom(slug: string | null, version?: number) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (slug) {
          next.set("room", version ? `${slug}/${version}` : slug);
          next.delete("inspect");
        } else next.delete("room");
        return next;
      },
      { replace: true },
    );
  }
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

  /** Follow one turn's events; resolves to its refusal (or its stop) in words, or `null`. */
  async function follow(
    run: (onEvent: (event: TurnEvent) => void, signal: AbortSignal) => Promise<void>,
  ): Promise<string | null> {
    setRunning({ working: null, tool: null });
    setSpecialists([]);
    setKept([]);
    const controller = new AbortController();
    stream.current = controller;
    let refused: string | null = null;
    try {
      await run((event) => {
        if (event.event === "specialist") setRunning({ working: event.data.role, tool: null });
        else if (event.event === "tool") setRunning((now) => ({ working: now?.working ?? null, tool: event.data.plugin }));
        else if (event.event === "reply" || event.event === "pending") setSpecialists(event.data.specialists);
        else if (event.event === "title") {
          queryClient.setQueryData<ThreadDetail>(["thread", threadId], (old) => (old ? { ...old, title: event.data.title } : old));
        } else if (event.event === "rewound") setKept(event.data.kept);
        else if (event.event === "error") refused = event.data.reason;
        else if (event.event === "stopped") refused = event.data.text;
      }, controller.signal);
    } catch (error) {
      refused = controller.signal.aborted ? "Stopped." : (message(error) ?? "the turn failed");
    }
    stream.current = null;
    await refresh();
    setRunning(null);
    return refused;
  }

  async function stop() {
    try {
      await api.stopTurn(threadId);
    } catch {
      // No turn to stop on the server (it has just ended): stop following it here.
      stream.current?.abort();
    }
  }

  async function send(text: string, files: Upload[]): Promise<string | null> {
    const edited = editing;
    setEditing(null);
    atBottom.current = true;
    setOptimistic({ text, uploads: edited ? [] : files });
    const refused = await follow((onEvent, signal) =>
      edited
        ? api.streamEdit(threadId, edited.messageId, text, onEvent, signal)
        : api.streamTurn(threadId, text, files.map((u) => u.upload_id), onEvent, signal),
    );
    setOptimistic(null);
    return refused;
  }

  async function answer(pending: Pending, value: ResumeBody) {
    setAnswerError(null);
    atBottom.current = true;
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
  const lastOwner = messages.reduce((found, m, index) => (m.role === "owner" && m.message_id ? index : found), -1);
  const canEdit = running === null && !pending && !optimistic;
  // Shown only for the conversation's current room with a 3D model; a stale address shows nothing.
  const room = progress.data?.room;
  const roomAddress = parseRoom(params.get("room"));
  const roomShown =
    !inspected && room?.slug && room.model && room.surfaces && roomAddress?.slug === room.slug ? room : null;
  // The chosen version, or the latest when the address names none or one no longer listed.
  const roomVersions = roomShown?.versions ?? [];
  const roomVersion = roomVersions.find((v) => v.version === roomAddress?.version) ?? roomVersions[0];
  const roomModel = roomVersion
    ? { model: roomVersion.model, surfaces: roomVersion.surfaces, dimensions: roomVersion.dimensions }
    : { model: roomShown?.model ?? null, surfaces: roomShown?.surfaces ?? null, dimensions: null };

  return (
    <div className="flex">
      <Rail
        open={panel}
        onOpen={setPanel}
        panels={[
          { id: "tools", label: "Tools", icon: "tools", content: <Tools threadId={threadId} /> },
          { id: "notes", label: "Decisions so far", icon: "notes", content: <DecisionsNote threadId={threadId} /> },
          {
            id: "project",
            label: "Project",
            icon: "project",
            content: (
              <ProjectPanel
                threadId={threadId}
                progress={progress}
                onInspect={inspect}
                onInspectRoom={inspectRoom}
                onDeleted={deleted}
              />
            ),
          },
        ]}
      />
      <Page wide>
        <p><Link to="/conversations" className="underline">All conversations</Link></p>
        <Title key={thread.data.title} threadId={threadId} title={thread.data.title} />
        <div
          className={inspected || roomShown ? "grid gap-4 lg:grid-cols-2 lg:items-start" : "mx-auto max-w-5xl"}
          // The window height left under the header and the title, less the page's bottom padding:
          // the chat column's height, and the inspector's at most beside it.
          style={{ "--chat-h": `calc(100vh - ${columnTop}px - 2rem)` } as CSSProperties}
        >
          <div
            ref={column}
            className="flex h-(--chat-h) min-w-0 flex-col gap-4"
          >
            <section
              ref={list}
              onScroll={onScroll}
              className={`${cardClass} min-h-48 flex-1 space-y-4 overflow-y-auto`}
              aria-label="Messages"
            >
              {messages.length === 0 && !optimistic && <p className="text-muted-foreground">Nothing said yet. Describe the piece you want.</p>}
              {messages.map((m, index) => {
                if (m.role === "confirmation") {
                  return (
                    <p key={index} className="mx-auto w-fit rounded-md border px-3 py-2 text-sm text-muted-foreground" data-role="confirmation">
                      Answered: {m.text}
                    </p>
                  );
                }
                if (m.role === "notice") return <Notice key={index} m={m} onReview={inspect} />;
                if (m.kind === "answers") {
                  return (
                    <div key={index} className="mx-auto w-full max-w-xl" data-role="answers">
                      <AnswersTable rows={m.rows ?? []} />
                    </div>
                  );
                }
                if (m.role === "owner") {
                  const editable = canEdit && index === lastOwner && editing === null;
                  return (
                    <OwnerMessage
                      key={index}
                      m={m}
                      uploadById={uploadById}
                      onEdit={editable ? () => setEditing({ messageId: m.message_id as string, text: m.text }) : undefined}
                    />
                  );
                }
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
              {kept.length > 0 && (
                <p role="status" className="text-sm text-muted-foreground">
                  Kept from the replaced message: {kept.join("; ")}.
                </p>
              )}
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
              <Composer
                threadId={threadId}
                running={running !== null}
                onSend={send}
                onStop={() => void stop()}
                editing={editing}
                onCancelEdit={() => setEditing(null)}
              />
            )}
          </div>
          {inspected && (
            <aside aria-label="Inspector" className={paneClass}>
              <div className="flex items-center justify-between gap-2">
                <h2>{inspectedSpec.data?.name || inspected.packageId}</h2>
                <Button type="button" variant="ghost" size="sm" aria-label="Close inspector" onClick={() => inspect(null)}>
                  <X aria-hidden size={16} />
                </Button>
              </div>
              {/* Keyed by piece only: following a new version keeps the view and its notice. */}
              <InspectorView
                key={inspected.packageId}
                packageId={inspected.packageId}
                version={inspected.version}
                compact
                onChoose={(next) => inspect(inspected.packageId, next)}
              />
            </aside>
          )}
          {roomShown && (
            <aside aria-label="Room view" className={paneClass}>
              <div className="flex items-center justify-between gap-2">
                <h2>{roomShown.name}</h2>
                <Button type="button" variant="ghost" size="sm" aria-label="Close room view" onClick={() => inspectRoom(null)}>
                  <X aria-hidden size={16} />
                </Button>
              </div>
              {roomVersions.length > 0 && roomVersion && (
                <VersionSelect
                  name={roomShown.name}
                  versions={roomVersions}
                  value={roomVersion.version}
                  onChange={(next) => inspectRoom(roomShown.slug, next)}
                />
              )}
              {roomModel.model && roomModel.surfaces ? (
                <RoomView
                  key={roomModel.model}
                  name={roomShown.name}
                  model={roomModel.model}
                  report={roomModel.surfaces}
                  dimensions={roomModel.dimensions}
                  apartment={roomShown.scope === "apartment"}
                />
              ) : (
                <p className="text-sm text-muted-foreground">
                  Version {roomVersion?.version} of {roomShown.name} has no 3D view. Composing {roomShown.name} again
                  adds it.
                </p>
              )}
            </aside>
          )}
        </div>
      </Page>
    </div>
  );
}
