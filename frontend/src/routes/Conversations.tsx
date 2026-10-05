import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Thread, type ToolToggle } from "../lib/api";

function Tools({ thread }: { thread: Thread }) {
  const queryClient = useQueryClient();
  const tools = useQuery({ queryKey: ["tools", thread.thread_id], queryFn: () => api.tools(thread.thread_id) });
  const toggle = useMutation({
    mutationFn: ({ plugin, enabled }: { plugin: string; enabled: boolean }) =>
      api.setTool(thread.thread_id, plugin, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tools", thread.thread_id] }),
  });

  if (tools.isLoading) return <p>Loading tools…</p>;
  if (!tools.data) return null;

  return (
    <ul>
      {tools.data.map((tool: ToolToggle) => (
        <li key={tool.plugin} className="row">
          <div>
            <strong>{tool.plugin.replaceAll("_", " ")}</strong>
            <div>{tool.description}</div>
            {!tool.toggleable && <small>Always on</small>}
          </div>
          <label>
            <input
              type="checkbox"
              checked={tool.enabled}
              disabled={!tool.toggleable}
              aria-label={tool.plugin}
              onChange={(event) => toggle.mutate({ plugin: tool.plugin, enabled: event.target.checked })}
            />
          </label>
        </li>
      ))}
    </ul>
  );
}

export default function Conversations() {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("New conversation");
  const threads = useQuery({ queryKey: ["threads"], queryFn: api.threads });
  const create = useMutation({
    mutationFn: () => api.createThread(title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["threads"] }),
  });

  return (
    <main>
      <h1>Conversations</h1>
      <form
        className="row"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        <input value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Conversation title" />
        <button type="submit">Start</button>
      </form>
      {threads.data?.map((thread) => (
        <section key={thread.thread_id} className="card">
          <h2>{thread.title || "Untitled"}</h2>
          <Tools thread={thread} />
        </section>
      ))}
    </main>
  );
}
