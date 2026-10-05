import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";

export default function Plugins() {
  const queryClient = useQueryClient();
  const plugins = useQuery({ queryKey: ["admin-plugins"], queryFn: api.plugins });
  const toggle = useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) => api.setPlugin(name, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-plugins"] }),
  });

  if (!plugins.data) return <main>Loading…</main>;

  return (
    <main>
      <h1>Plugins</h1>
      {plugins.data.map((plugin) => (
        <section key={plugin.name} className="card">
          <div className="row">
            <div>
              <h2>{plugin.name}</h2>
              <p>{plugin.description}</p>
              <small>
                {plugin.kind} · {plugin.role} · {plugin.tools.join(", ")}
              </small>
            </div>
            <label>
              Enabled
              <input
                type="checkbox"
                checked={plugin.enabled}
                aria-label={`enable ${plugin.name}`}
                onChange={(event) => toggle.mutate({ name: plugin.name, enabled: event.target.checked })}
              />
            </label>
          </div>
        </section>
      ))}
    </main>
  );
}
