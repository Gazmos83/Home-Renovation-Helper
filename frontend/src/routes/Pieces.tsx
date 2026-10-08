import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, downloads, type RenderItem } from "../lib/api";
import { FieldError } from "../lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";

function message(error: unknown): string | null {
  return error instanceof Error ? error.message : null;
}

function RenderCard({ packageId, version, item }: { packageId: string; version: number; item: RenderItem }) {
  const queryClient = useQueryClient();
  const key = ["renders", packageId, version];
  const [comment, setComment] = useState(item.comment ?? "");
  const rate = useMutation({
    mutationFn: ({ rating, text }: { rating: "up" | "down"; text: string | null }) =>
      api.rateRender(packageId, version, item.render, rating, text),
    onMutate: async ({ rating, text }) => {
      await queryClient.cancelQueries({ queryKey: key });
      const before = queryClient.getQueryData<RenderItem[]>(key);
      queryClient.setQueryData<RenderItem[]>(key, (items) =>
        (items ?? []).map((i) => (i.render === item.render ? { ...i, rating, comment: text } : i)),
      );
      return { before };
    },
    onError: (_error, _vars, context) => queryClient.setQueryData(key, context?.before),
    onSettled: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const clear = useMutation({
    mutationFn: () => api.clearRating(packageId, version, item.render),
    onSuccess: () => {
      setComment("");
      queryClient.invalidateQueries({ queryKey: key });
    },
  });
  const failure = rate.error ?? clear.error;

  function give(rating: "up" | "down") {
    rate.mutate({ rating, text: comment.trim() || null });
  }

  return (
    <section className={cardClass} aria-label={item.label}>
      <div className="flex items-center gap-2">
        <h3>{item.label}</h3>
        {item.tier && <Badge variant="secondary">{item.tier}</Badge>}
      </div>
      <img src={item.preview} alt={`${item.label} of ${packageId} version ${version}`} className="max-h-72 rounded-md border" />
      {item.can_rate ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant={item.rating === "up" ? "default" : "outline"}
            aria-pressed={item.rating === "up"}
            aria-label={`Thumbs up ${item.label}`}
            onClick={() => give("up")}
          >
            <ThumbsUp aria-hidden size={16} />
          </Button>
          <Button
            type="button"
            variant={item.rating === "down" ? "default" : "outline"}
            aria-pressed={item.rating === "down"}
            aria-label={`Thumbs down ${item.label}`}
            onClick={() => give("down")}
          >
            <ThumbsDown aria-hidden size={16} />
          </Button>
          <Input
            aria-label={`Comment on ${item.label}`}
            value={comment}
            placeholder="What did you think?"
            onChange={(event) => setComment(event.target.value)}
            onBlur={() => item.rating && comment.trim() !== (item.comment ?? "") && give(item.rating)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && item.rating) give(item.rating);
            }}
          />
          {item.rating && (
            <Button type="button" variant="ghost" onClick={() => clear.mutate()}>
              Clear rating of {item.label}
            </Button>
          )}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Rendered before ratings existed — render it again to rate it.
        </p>
      )}
      <FieldError message={failure instanceof ApiError || failure instanceof Error ? failure.message : null} />
    </section>
  );
}

function Approval({ packageId, version }: { packageId: string; version: number }) {
  const queryClient = useQueryClient();
  const info = useQuery({
    queryKey: ["version", packageId, version],
    queryFn: () => api.version(packageId, version),
  });
  const change = useMutation({
    mutationFn: (approve: boolean) =>
      approve ? api.approveVersion(packageId, version) : api.unapproveVersion(packageId, version),
    onSuccess: () => {
      // Approving one version clears another, so every version of the piece is read again.
      queryClient.invalidateQueries({ queryKey: ["version", packageId] });
      queryClient.invalidateQueries({ queryKey: ["progress"] });
    },
  });
  // No control until the version is read, and none for a version that is not built.
  if (!info.data || info.data.status !== "succeeded") return null;
  const approved = info.data.approved_at !== null;
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={`Approval of ${packageId} version ${version}`}>
      {approved && <Badge>Approved</Badge>}
      <Button type="button" variant={approved ? "outline" : "default"} disabled={change.isPending} onClick={() => change.mutate(!approved)}>
        {approved ? "Unapprove" : "Approve"} version {version}
      </Button>
      <FieldError message={message(change.error)} />
    </div>
  );
}

function Downloads({ packageId, version }: { packageId: string; version: number }) {
  const info = useQuery({
    queryKey: ["version", packageId, version],
    queryFn: () => api.version(packageId, version),
  });
  return (
    <p className="flex flex-wrap gap-4 text-sm">
      <a href={downloads.design(packageId, version)} download={`${packageId}-v${version}.json`} className="underline">
        Download design (version {version})
      </a>
      {info.data?.status === "succeeded" && (
        <a href={downloads.bundle(packageId, version)} download={`${packageId}-v${version}.zip`} className="underline">
          Download bundle (version {version})
        </a>
      )}
      {info.data?.status === "succeeded" && (
        <Link to={`/pieces/${encodeURIComponent(packageId)}/versions/${version}`} className="underline">
          Inspect version {version}
        </Link>
      )}
    </p>
  );
}

function Version({ packageId, version }: { packageId: string; version: number }) {
  const renders = useQuery({
    queryKey: ["renders", packageId, version],
    queryFn: () => api.renders(packageId, version),
  });
  let shown;
  if (renders.error) shown = <FieldError message={message(renders.error)} />;
  else if (!renders.data) shown = <p>Loading…</p>;
  else if (renders.data.length === 0) shown = <p>No renders of this version yet.</p>;
  else {
    shown = (
      <div className="grid gap-4 sm:grid-cols-2">
        {renders.data.map((item) => (
          <RenderCard key={item.render} packageId={packageId} version={version} item={item} />
        ))}
      </div>
    );
  }
  return (
    <div className="grid gap-4">
      <Approval packageId={packageId} version={version} />
      <Downloads packageId={packageId} version={version} />
      {shown}
    </div>
  );
}

const NO_ROOM = "";

/** The room a piece is in, with a selector to attach it, move it or clear it. */
function RoomPicker({ id, room }: { id: string; room: string | null }) {
  const queryClient = useQueryClient();
  const rooms = useQuery({ queryKey: ["rooms"], queryFn: api.rooms });
  const choose = useMutation({
    mutationFn: (name: string) => api.setPieceRoom(id, name === NO_ROOM ? null : name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pieces"] }),
  });
  const label = `Room of ${id}`;
  return (
    <div className="grid gap-1">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span>{room ? `Room: ${room}` : "No room"}</span>
        <Select
          aria-label={label}
          className="w-auto"
          value={room ?? NO_ROOM}
          disabled={choose.isPending}
          onChange={(event) => choose.mutate(event.target.value)}
        >
          <option value={NO_ROOM}>No room</option>
          {(rooms.data ?? []).map((room) => (
            <option key={room.name} value={room.name}>
              {room.name}
            </option>
          ))}
        </Select>
      </div>
      <FieldError message={message(choose.error)} />
    </div>
  );
}

function Piece({ id, versions, room }: { id: string; versions: number[]; room: string | null }) {
  const [version, setVersion] = useState(versions[0]);
  const infos = useQueries({
    queries: versions.map((n) => ({
      queryKey: ["version", id, n],
      queryFn: () => api.version(id, n),
    })),
  });
  const approved = infos.find((q) => q.data?.approved_at)?.data?.version;
  return (
    <section className={cardClass} aria-label={id}>
      <h2>{id}</h2>
      <p className="text-sm text-muted-foreground">
        {approved ? `Approved: version ${approved}` : "No version approved yet."}
      </p>
      <RoomPicker id={id} room={room} />
      <div className="flex flex-wrap gap-2" role="group" aria-label={`Versions of ${id}`}>
        {versions.map((n) => (
          <Button
            key={n}
            type="button"
            size="sm"
            variant={n === version ? "default" : "outline"}
            aria-pressed={n === version}
            onClick={() => setVersion(n)}
          >
            Version {n}
          </Button>
        ))}
      </div>
      <Version packageId={id} version={version} />
    </section>
  );
}

export default function Pieces() {
  const pieces = useQuery({ queryKey: ["pieces"], queryFn: api.pieces });
  if (pieces.error) {
    return (
      <Page>
        <h1>Pieces</h1>
        <FieldError message={message(pieces.error)} />
      </Page>
    );
  }
  if (!pieces.data) return <Page>Loading…</Page>;
  return (
    <Page>
      <h1>Pieces</h1>
      <p>Your designs and their renders. Tell us what you think of a render; it helps the next one.</p>
      <p className="text-sm">
        <a href={downloads.importTemplate} download="import-template.json" className="underline">
          Download the import template
        </a>{" "}
        — give it to another AI chat to fill in, then attach the file it returns in a new conversation.
      </p>
      {pieces.data.length === 0 && <p>No pieces yet. Describe one in a conversation.</p>}
      {pieces.data.map((piece) => (
        <Piece key={piece.package_id} id={piece.package_id} versions={piece.versions} room={piece.room} />
      ))}
    </Page>
  );
}
