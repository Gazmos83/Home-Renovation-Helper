import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { FieldError } from "@/lib/form";
import { Button } from "@/components/ui/button";

/**
 * "Delete piece", asked in place before anything is deleted (delete-piece). The question lists what
 * goes, read from the service; a refusal is shown instead of "Yes". Only "Yes" sends the delete.
 */
export function DeletePiece({ packageId, onDeleted }: { packageId: string; onDeleted: () => void }) {
  const [asking, setAsking] = useState(false);
  const summary = useQuery({
    queryKey: ["piece-deletion", packageId],
    queryFn: () => api.pieceDeletion(packageId),
    enabled: asking,
    staleTime: 0,
  });
  const remove = useMutation({
    mutationFn: () => api.deletePiece(packageId),
    onSuccess: () => {
      setAsking(false);
      onDeleted();
    },
  });
  const refusal = remove.error instanceof Error ? remove.error.message : null;

  if (!asking) {
    return (
      <div className="grid gap-1">
        <div>
          <Button type="button" size="sm" variant="outline" onClick={() => setAsking(true)}>
            Delete piece
          </Button>
        </div>
        <FieldError message={refusal} />
      </div>
    );
  }
  const data = summary.data;
  const count = data?.conversations.length ?? 0;
  return (
    <div className="grid gap-2 rounded-md border p-2" role="group" aria-label="Delete piece">
      {summary.error instanceof Error && <FieldError message={summary.error.message} />}
      {!data && !summary.error && <p className="text-sm">Loading…</p>}
      {data && (
        <div className="grid gap-1 text-sm">
          <p>
            Are you sure? {data.name} and all its {data.versions.length} versions will be deleted with their renders,
            reviews and pricings.
          </p>
          {data.approved.map((a) => (
            <p key={a.version}>
              Approved: version {a.version}, {a.priced ? "priced" : "not priced"}
            </p>
          ))}
          {count > 0 && <p>Its {count} {count === 1 ? "conversation" : "conversations"} will be deleted too.</p>}
          <p>This cannot be undone.</p>
        </div>
      )}
      {data?.refusal && <FieldError message={data.refusal} />}
      <div className="flex flex-wrap gap-2">
        {data && !data.refusal && (
          <Button type="button" size="sm" variant="destructive" disabled={remove.isPending} onClick={() => remove.mutate()}>
            Yes, delete {data.name}
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={remove.isPending}
          onClick={() => {
            remove.reset();
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
