import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";

export default function Plugins() {
  const queryClient = useQueryClient();
  const plugins = useQuery({ queryKey: ["admin-plugins"], queryFn: api.plugins });
  const toggle = useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) => api.setPlugin(name, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-plugins"] }),
  });

  if (!plugins.data) return <Page>Loading…</Page>;

  return (
    <Page>
      <h1>Plugins</h1>
      {plugins.data.map((plugin) => (
        <section key={plugin.name} className={cardClass}>
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2>{plugin.name}</h2>
              <p>{plugin.description}</p>
              <small className="text-muted-foreground">
                {plugin.kind} · {plugin.role} · {plugin.tools.join(", ")}
              </small>
            </div>
            <Label>
              Enabled
              <Input
                type="checkbox"
                checked={plugin.enabled}
                aria-label={`enable ${plugin.name}`}
                onChange={(event) => toggle.mutate({ name: plugin.name, enabled: event.target.checked })}
              />
            </Label>
          </div>
        </section>
      ))}
    </Page>
  );
}
