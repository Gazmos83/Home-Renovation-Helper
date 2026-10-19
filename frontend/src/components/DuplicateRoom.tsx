import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { FieldError } from "@/lib/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

/**
 * "Duplicate room", asked in place like "Delete room" (duplicate-room). The owner names the copy and
 * picks one layout version (the latest preselected) or none; only "Duplicate" sends the request.
 * A refusal keeps the form open.
 */
export function DuplicateRoom({ room, versions }: { room: string; versions: number[] }) {
  const queryClient = useQueryClient();
  const newestFirst = [...versions].sort((a, b) => b - a);
  const [asking, setAsking] = useState(false);
  const [name, setName] = useState(`${room} (copy)`);
  // "" is "No layout".
  const [version, setVersion] = useState(newestFirst.length > 0 ? String(newestFirst[0]) : "");
  const duplicate = useMutation({
    mutationFn: () => api.duplicateRoom(room, { name: name.trim(), version: version ? Number(version) : null }),
    onSuccess: () => {
      setAsking(false);
      for (const key of ["rooms", "compositions"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  const refusal = duplicate.error instanceof Error ? duplicate.error.message : null;

  if (!asking) {
    return (
      <div>
        <Button type="button" size="sm" variant="outline" onClick={() => setAsking(true)}>
          Duplicate room
        </Button>
      </div>
    );
  }
  return (
    <div className="grid gap-2 rounded-md border p-2" role="group" aria-label="Duplicate room">
      <label className="grid gap-1 text-sm">
        Name of the copy
        <Input value={name} onChange={(event) => setName(event.target.value)} />
      </label>
      {newestFirst.length > 0 && (
        <label className="grid gap-1 text-sm">
          Layout to copy
          <Select className="w-auto max-w-full min-w-0" value={version} onChange={(event) => setVersion(event.target.value)}>
            {newestFirst.map((n) => (
              <option key={n} value={String(n)}>
                Version {n}
              </option>
            ))}
            <option value="">No layout</option>
          </Select>
        </label>
      )}
      <p className="text-sm text-muted-foreground">{room} is not changed.</p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" disabled={duplicate.isPending || !name.trim()} onClick={() => duplicate.mutate()}>
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
