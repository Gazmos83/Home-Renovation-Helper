import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { FieldError } from "../lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";

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
      {threads.data?.map((thread) => (
        <Link key={thread.thread_id} to={`/conversations/${thread.thread_id}`} className={`${cardClass} block hover:bg-accent`}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2>{thread.title || "Untitled"}</h2>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {thread.package_id && <Badge variant="secondary">{thread.package_id}</Badge>}
              <time dateTime={thread.last_turn_at}>{new Date(thread.last_turn_at).toLocaleString()}</time>
            </div>
          </div>
        </Link>
      ))}
    </Page>
  );
}
