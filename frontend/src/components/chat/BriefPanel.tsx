import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Brief } from "../../lib/api";
import { FieldError } from "../../lib/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Form = { room: string; purpose: string; height: string; style: string; budget: string };

const fromBrief = (brief: Brief): Form => ({
  room: brief.room ?? "",
  purpose: brief.purpose ?? "",
  height: brief.max_piece_height_mm?.toString() ?? "",
  style: brief.style ?? "",
  budget: brief.budget_eur?.toString() ?? "",
});

/** A blank number field is no value; anything else must be a number. */
function number(text: string): number | null | undefined {
  if (!text.trim()) return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : undefined;
}

/** The conversation's brief settings, listed and editable (split-project-panel). */
export function BriefPanel({ threadId }: { threadId: string }) {
  const queryClient = useQueryClient();
  const key = ["brief", threadId];
  const brief = useQuery({ queryKey: key, queryFn: () => api.brief(threadId) });
  const [form, setForm] = useState<Form | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const save = useMutation({
    mutationFn: (body: Parameters<typeof api.saveBrief>[1]) => api.saveBrief(threadId, body),
    onSuccess: (value) => {
      queryClient.setQueryData(key, value);
      queryClient.invalidateQueries({ queryKey: ["progress", threadId] });
      setForm(null);
      setSaved(true);
    },
  });

  if (brief.error) return <FieldError message={brief.error instanceof Error ? brief.error.message : null} />;
  if (!brief.data) return <p className="text-sm text-muted-foreground">Loading…</p>;
  const values = form ?? fromBrief(brief.data);
  const change = (patch: Partial<Form>) => {
    setSaved(false);
    setProblem(null);
    setForm({ ...values, ...patch });
  };

  function submit() {
    const height = number(values.height);
    const budget = number(values.budget);
    if (!values.purpose.trim()) return setProblem("The purpose is required.");
    if (height === undefined || (height !== null && height <= 0)) return setProblem("The highest the piece may be must be a number above 0.");
    if (budget === undefined || (budget !== null && budget < 0)) return setProblem("The budget must be a number, 0 or more.");
    setProblem(null);
    save.mutate({
      room: values.room || null,
      purpose: values.purpose.trim(),
      max_piece_height_mm: height,
      style: values.style.trim() || null,
      budget_eur: budget,
    });
  }

  const rooms = brief.data.rooms.includes(values.room) || !values.room ? brief.data.rooms : [values.room, ...brief.data.rooms];
  return (
    <form
      className="space-y-3"
      aria-label="Brief"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      {!brief.data.confirmed && (
        <p className="text-sm text-muted-foreground">No brief yet. Describe the piece in the chat, or fill this in.</p>
      )}
      <div className="space-y-1">
        <Label htmlFor="brief-room">Room</Label>
        <select
          id="brief-room"
          className="w-full rounded-md border bg-background px-2 py-1 text-sm"
          value={values.room}
          onChange={(event) => change({ room: event.target.value })}
        >
          <option value="">No room</option>
          {rooms.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-1">
        <Label htmlFor="brief-purpose">Purpose</Label>
        <textarea
          id="brief-purpose"
          className="w-full rounded-md border bg-background px-2 py-1 text-sm"
          rows={3}
          maxLength={2000}
          value={values.purpose}
          onChange={(event) => change({ purpose: event.target.value })}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="brief-height">Highest the piece may be (mm)</Label>
        <Input
          id="brief-height"
          inputMode="decimal"
          value={values.height}
          onChange={(event) => change({ height: event.target.value })}
        />
        {brief.data.max_piece_height_from_version !== null && form === null && (
          <p className="text-xs text-muted-foreground">
            Raised by approving version {brief.data.max_piece_height_from_version}.
          </p>
        )}
      </div>
      <div className="space-y-1">
        <Label htmlFor="brief-style">Style</Label>
        <Input id="brief-style" maxLength={500} value={values.style} onChange={(event) => change({ style: event.target.value })} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="brief-budget">Budget (EUR)</Label>
        <Input
          id="brief-budget"
          inputMode="decimal"
          value={values.budget}
          onChange={(event) => change({ budget: event.target.value })}
        />
      </div>
      <div className="flex items-center gap-2">
        <Button type="submit" size="sm" disabled={save.isPending}>
          Save
        </Button>
        {saved && <span className="text-sm text-muted-foreground">Saved.</span>}
      </div>
      {problem && <p className="text-sm text-destructive">{problem}</p>}
      <FieldError message={save.error instanceof Error ? save.error.message : null} />
    </form>
  );
}
