import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { FieldError } from "@/lib/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

/** A name made into a package id, as the service makes it ("Sideboard (copy)" → "sideboard-copy"). */
export function idFromName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64)
    .replace(/-+$/, "");
}

/**
 * "Duplicate piece", asked in place like "Delete piece" (duplicate-piece). The owner picks the version,
 * the copy's name and its id; only "Duplicate" sends the request. A refusal keeps the form open.
 */
export function DuplicatePiece({
  packageId,
  versions,
  onDuplicated,
}: {
  packageId: string;
  versions: number[];
  onDuplicated: (threadId: string) => void;
}) {
  const [asking, setAsking] = useState(false);
  const [version, setVersion] = useState(versions[0]);
  const [name, setName] = useState<string | null>(null);
  const [id, setId] = useState<string | null>(null);
  // The piece's name, for the prefilled copy name; a piece without a record falls back to its id.
  const summary = useQuery({
    queryKey: ["piece-deletion", packageId],
    queryFn: () => api.pieceDeletion(packageId),
    enabled: asking,
    staleTime: 0,
    retry: false,
  });
  const shownName = name ?? (summary.data || summary.error ? `${summary.data?.name ?? packageId} (copy)` : "");
  const shownId = id ?? idFromName(shownName);
  const duplicate = useMutation({
    mutationFn: () => api.duplicatePiece(packageId, { version, name: shownName.trim(), package_id: shownId }),
    onSuccess: (created) => {
      setAsking(false);
      onDuplicated(created.thread_id);
    },
  });
  const refusal = duplicate.error instanceof Error ? duplicate.error.message : null;

  if (!asking) {
    return (
      <div>
        <Button type="button" size="sm" variant="outline" onClick={() => setAsking(true)}>
          Duplicate piece
        </Button>
      </div>
    );
  }
  return (
    <div className="grid gap-2 rounded-md border p-2" role="group" aria-label="Duplicate piece">
      <label className="grid gap-1 text-sm">
        Version to copy
        <Select className="w-auto max-w-full min-w-0" value={version} onChange={(event) => setVersion(Number(event.target.value))}>
          {versions.map((n) => (
            <option key={n} value={n}>
              Version {n}
            </option>
          ))}
        </Select>
      </label>
      <label className="grid gap-1 text-sm">
        Name of the copy
        <Input value={shownName} onChange={(event) => setName(event.target.value)} />
      </label>
      <label className="grid gap-1 text-sm">
        Id of the copy
        <Input value={shownId} onChange={(event) => setId(event.target.value)} />
      </label>
      <p className="text-sm text-muted-foreground">The copy gets its own conversation; {packageId} is not changed.</p>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          disabled={duplicate.isPending || !shownName.trim() || !shownId}
          onClick={() => duplicate.mutate()}
        >
          Duplicate
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={duplicate.isPending}
          onClick={() => {
            duplicate.reset();
            setAsking(false);
          }}
        >
          Cancel
        </Button>
      </div>
      <FieldError message={refusal} />
    </div>
  );
}
