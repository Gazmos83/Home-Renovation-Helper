import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type MemoryPayload, type MemorySettings } from "../../lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cardClass } from "@/components/ui/card";

type Field = keyof MemorySettings;
type Row = { field: Field; label: string; kind: "number" | "text" | "bool" | "choice"; choices?: [string, string][]; unit?: string };

const GROUPS: { title: string; rows: Row[] }[] = [
  {
    title: "Compression",
    rows: [
      { field: "trigger_percent", label: "Start compressing at (share of the context budget)", kind: "number", unit: "%" },
      { field: "keep_turns", label: "Recent turns always kept in full", kind: "number" },
      { field: "recent_inputs", label: "Recent inputs sent in full (0 = the trigger decides)", kind: "number" },
      { field: "note_tokens", label: "Note length", kind: "number", unit: "tokens" },
      { field: "note_instructions", label: "Note headings and instructions", kind: "text" },
      { field: "tool_result_chars", label: "Tool result cut to", kind: "number", unit: "characters" },
    ],
  },
  {
    title: "What is saved",
    rows: [
      { field: "save_preferences", label: "Save style and budget from a confirmed brief", kind: "bool" },
    ],
  },
  {
    title: "What a conversation sees",
    rows: [
      { field: "other_builds", label: "Other builds of the conversation", kind: "choice", choices: [["line", "one line each"], ["hidden", "hidden"]] },
      { field: "include_preferences", label: "Preferences", kind: "bool" },
      { field: "include_review_items", label: "Latest review's open items", kind: "bool" },
      { field: "include_version_verdicts", label: "Open version verdicts (doesn't match)", kind: "bool" },
      { field: "render_ratings", label: "Latest render ratings given (0–10)", kind: "number" },
      { field: "include_extension_requests", label: "Open generator-extension requests", kind: "bool" },
    ],
  },
];

function shown(value: unknown): string {
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

function SettingRow({ row, payload, onSave, onReset }: {
  row: Row;
  payload: MemoryPayload;
  onSave: (changes: Partial<MemorySettings>) => void;
  onReset: (field: Field) => void;
}) {
  const value = payload.settings[row.field];
  const fallback = payload.defaults[row.field];
  const [draft, setDraft] = useState(String(value));
  const id = `memory-${row.field}`;
  const commit = (raw: string) => {
    const next = row.kind === "number" ? Number(raw) : row.kind === "bool" ? raw === "true" : raw;
    onSave({ [row.field]: next } as Partial<MemorySettings>);
  };
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>
        {row.label}
        {row.unit ? ` (${row.unit})` : ""}
      </Label>
      {row.kind === "text" ? (
        <textarea id={id} className="w-full rounded-md border px-3 py-2 text-sm" rows={5} value={draft} onChange={(e) => setDraft(e.target.value)} />
      ) : row.kind === "number" ? (
        <Input id={id} type="number" value={draft} onChange={(e) => setDraft(e.target.value)} />
      ) : (
        <Select id={id} value={String(value)} onChange={(e) => commit(e.target.value)}>
          {(row.kind === "bool" ? ([["true", "yes"], ["false", "no"]] as [string, string][]) : row.choices ?? []).map(([key, text]) => (
            <option key={key} value={key}>
              {text}
            </option>
          ))}
        </Select>
      )}
      <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        Default: {row.kind === "text" ? "the shipped instructions" : shown(fallback)}
        {(row.kind === "number" || row.kind === "text") && (
          <Button type="button" size="sm" variant="outline" onClick={() => commit(draft)}>
            Save
          </Button>
        )}
        {value !== fallback && (
          <Button type="button" size="sm" variant="ghost" aria-label={`Reset ${row.label}`} onClick={() => onReset(row.field)}>
            Reset
          </Button>
        )}
      </p>
    </div>
  );
}

/** Memory settings: compression, what is saved, what a conversation sees (conversation-memory-settings). */
export default function Memory() {
  const queryClient = useQueryClient();
  const memory = useQuery({ queryKey: ["admin-memory"], queryFn: api.memorySettings });
  const [error, setError] = useState<string | null>(null);
  const done = (payload: MemoryPayload) => {
    setError(null);
    queryClient.setQueryData(["admin-memory"], payload);
  };
  const save = useMutation({ mutationFn: api.saveMemorySettings, onSuccess: done, onError: (e: Error) => setError(e.message) });
  const reset = useMutation({ mutationFn: api.resetMemorySetting, onSuccess: done, onError: (e: Error) => setError(e.message) });

  if (!memory.data) return <>Loading…</>;
  const payload = memory.data;
  return (
    <>
      <p className="text-sm text-muted-foreground">
        Changes apply from the next call, without a restart. Every default is the behaviour before these settings.
        Summary calls are metered on the Foreman's model like any other call.
      </p>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {GROUPS.map((group) => (
        <section key={group.title} className={`${cardClass} space-y-4`}>
          <h2>{group.title}</h2>
          {group.rows.map((row) => (
            <SettingRow
              key={`${row.field}-${String(payload.settings[row.field])}`}
              row={row}
              payload={payload}
              onSave={(changes) => save.mutate(changes)}
              onReset={(field) => reset.mutate(field)}
            />
          ))}
        </section>
      ))}
      <section className={cardClass}>
        <h2>Fixed rules</h2>
        <ul className="list-disc pl-5 text-sm">
          {payload.fixed_rules.map((rule) => (
            <li key={rule}>{rule}</li>
          ))}
        </ul>
      </section>
    </>
  );
}
