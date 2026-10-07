import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { api, ApiError, type RenderItem } from "../lib/api";
import { FieldError } from "../lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
      {item.viewer && (
        <p>
          <a href={item.viewer} target="_blank" rel="noreferrer" className="underline">
            Open the {item.label.toLowerCase()} viewer
          </a>
        </p>
      )}
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

function Version({ packageId, version }: { packageId: string; version: number }) {
  const renders = useQuery({
    queryKey: ["renders", packageId, version],
    queryFn: () => api.renders(packageId, version),
  });
  if (renders.error) return <FieldError message={message(renders.error)} />;
  if (!renders.data) return <p>Loading…</p>;
  if (renders.data.length === 0) return <p>No renders of this version yet.</p>;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {renders.data.map((item) => (
        <RenderCard key={item.render} packageId={packageId} version={version} item={item} />
      ))}
    </div>
  );
}

function Piece({ id, versions }: { id: string; versions: number[] }) {
  const [version, setVersion] = useState(versions[0]);
  return (
    <section className={cardClass} aria-label={id}>
      <h2>{id}</h2>
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
      {pieces.data.length === 0 && <p>No pieces yet. Describe one in a conversation.</p>}
      {pieces.data.map((piece) => (
        <Piece key={piece.package_id} id={piece.package_id} versions={piece.versions} />
      ))}
    </Page>
  );
}
