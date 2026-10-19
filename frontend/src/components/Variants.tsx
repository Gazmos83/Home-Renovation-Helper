import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { api, type Variant } from "../lib/api";

/** The restyle pictures of one version. Appearance only: the note says so under every picture. */
export function Variants({ items }: { items: Variant[] }) {
  if (items.length === 0) return null;
  return (
    <section className="space-y-2" aria-label="Restyle pictures">
      <h3>Restyle pictures</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((item) => (
          <figure key={item.id} className="space-y-1 rounded-md border p-2">
            <img src={item.still} alt={`${item.label} restyle`} className="max-h-48 rounded-md border" />
            <figcaption className="space-y-1 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <strong>{item.label}</strong>
                {item.tier && <Badge variant="secondary">{item.tier}</Badge>}
              </span>
              {item.note && <span className="block text-muted-foreground">{item.note}</span>}
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}

/** A composition version's variants (view only: a composition has no style to keep). */
export function RoomVariants({ slug, version }: { slug: string; version: number }) {
  const variants = useQuery({
    queryKey: ["variants", "room", slug, version],
    queryFn: () => api.compositionVariants(slug, version),
    refetchInterval: 5000,
  });
  return <Variants items={variants.data ?? []} />;
}
