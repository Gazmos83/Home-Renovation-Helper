import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { api, ApiError, type RenderItem } from "@/lib/api";
import { FieldError } from "@/lib/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * The owner's rating of one render (feedback-capture): thumbs up or down with a comment, and
 * clearing it. The Pieces page and the inspector's Renders tab both use it, against the same
 * `["renders", packageId, version]` query.
 */
export function RenderRating({ packageId, version, item }: { packageId: string; version: number; item: RenderItem }) {
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
    <>
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
    </>
  );
}
