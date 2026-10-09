import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { FieldError } from "@/lib/form";
import { Button } from "@/components/ui/button";

/**
 * "Delete version N", asked in place before anything is deleted (version-cleanup-and-inspection).
 * Only "Yes" sends the delete; a refusal is shown with its reason next to the control.
 * `only` says the version is the piece's last, so the whole piece goes with it.
 */
export function DeleteVersion({
  packageId,
  version,
  only = false,
  onDeleted,
}: {
  packageId: string;
  version: number;
  only?: boolean;
  onDeleted: () => void;
}) {
  const [asking, setAsking] = useState(false);
  const remove = useMutation({
    mutationFn: () => api.deleteVersion(packageId, version),
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
            Delete version {version}
          </Button>
        </div>
        <FieldError message={refusal} />
      </div>
    );
  }
  return (
    <div className="grid gap-2 rounded-md border p-2" role="group" aria-label={`Delete version ${version}`}>
      <p className="text-sm">
        {only
          ? `Are you sure? Version ${version} is the only version of ${packageId}, so the whole piece will be deleted with its renders, reviews and pricings. This cannot be undone.`
          : `Are you sure? Version ${version} and its renders, reviews and pricings will be deleted. This cannot be undone.`}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="destructive" disabled={remove.isPending} onClick={() => remove.mutate()}>
          Yes, delete version {version}
        </Button>
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
