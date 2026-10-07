import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Thread } from "../lib/api";
import { FieldError } from "../lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";

/** One conversation in the list, with its delete action (piece-versions-and-chat-delete). */
function Entry({ thread }: { thread: Thread }) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const name = thread.title || "Untitled";
  const remove = useMutation({
    mutationFn: () => api.deleteThread(thread.thread_id),
    onSuccess: () => {
      // Only what the list shows changes: the conversation is gone, its pieces stay.
      queryClient.setQueryData<Thread[]>(["threads"], (list) => list?.filter((t) => t.thread_id !== thread.thread_id));
      queryClient.invalidateQueries({ queryKey: ["threads"] });
    },
  });
  return (
    <section className={`${cardClass} grid gap-2`} aria-label={name}>
      <Link to={`/conversations/${thread.thread_id}`} className="block rounded-md hover:bg-accent">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2>{name}</h2>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {thread.package_id && <Badge variant="secondary">{thread.package_id}</Badge>}
            <time dateTime={thread.last_turn_at}>{new Date(thread.last_turn_at).toLocaleString()}</time>
          </div>
        </div>
      </Link>
      {confirming ? (
        <div className="grid gap-2" role="group" aria-label={`Delete ${name}?`}>
          <p className="text-sm">
            Delete “{name}”? Its messages and attached files go; its pieces and renders are kept. A deleted
            conversation cannot be restored.
          </p>
          <div className="flex gap-2">
            <Button type="button" variant="destructive" disabled={remove.isPending} onClick={() => remove.mutate()}>
              Delete
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setConfirming(false);
                remove.reset();
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div>
          <Button type="button" variant="ghost" size="sm" onClick={() => setConfirming(true)}>
            Delete {name}
          </Button>
        </div>
      )}
      <FieldError message={remove.error instanceof Error ? remove.error.message : null} />
    </section>
  );
}

export default function Conversations() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [title, setTitle] = useState("New conversation");
  const threads = useQuery({ queryKey: ["threads"], queryFn: api.threads });
  const create = useMutation({
    mutationFn: () => api.createThread(title),
    onSuccess: (thread) => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      navigate(`/conversations/${thread.thread_id}`);
    },
  });

  return (
    <Page>
      <h1>Conversations</h1>
      <form
        className="flex items-center justify-between gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        <Input value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Conversation title" />
        <Button type="submit">Start</Button>
      </form>
      <FieldError message={create.error instanceof Error ? create.error.message : null} />
      {threads.data?.length === 0 && <p>No conversations yet. Start one above and describe what you want.</p>}
      {threads.data?.map((thread) => <Entry key={thread.thread_id} thread={thread} />)}
    </Page>
  );
}
