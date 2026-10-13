import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, type Variant } from "../lib/api";

/** The request a piece variant becomes when the owner keeps its look: the Designer's usual revision follows. */
export function keepLookRequest(packageId: string, version: number, variant: Variant): string {
  const slots = Object.entries(variant.looks ?? {})
    .map(([slot, look]) => `${slot} as ${look}`)
    .join(", ");
  return (
    `I like the restyle picture "${variant.label}" of ${packageId} version ${version}. ` +
    `Please revise it so that ${slots}. That was appearance only, so ask me which real material to use ` +
    `and whether it is priced before you change anything.`
  );
}

/** The restyle pictures of one version. Appearance only: the note says so under every picture. */
export function Variants({
  items,
  onUse,
}: {
  items: Variant[];
  /** Keep this look: only for a piece, where it starts a revision the owner confirms. */
  onUse?: (variant: Variant) => void;
}) {
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
              {onUse && item.looks && (
                <Button type="button" size="sm" variant="outline" onClick={() => onUse(item)}>
                  Use this look
                </Button>
              )}
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}

/** A piece version's variants, fetched; nothing shows while there are none. */
export function PieceVariants({
  packageId,
  version,
  onUse,
}: {
  packageId: string;
  version: number;
  onUse?: (variant: Variant) => void;
}) {
  const variants = useQuery({
    queryKey: ["variants", packageId, version],
    queryFn: () => api.variants(packageId, version),
    refetchInterval: 5000,
  });
  return <Variants items={variants.data ?? []} onUse={onUse} />;
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
