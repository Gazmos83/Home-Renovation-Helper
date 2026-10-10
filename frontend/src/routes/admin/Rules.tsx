import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type DesignRule, type DesignRulesPayload } from "../../lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";

const ORIGIN: Record<DesignRule["origin"], string> = {
  file: "checked-in table",
  edited: "checked-in table, edited here",
  panel: "added here",
};

type Draft = {
  id: string;
  check: string;
  params: string;
  severity: "warn" | "refuse";
  publication: string;
  section: string;
  quote: string;
};

const EMPTY: Draft = { id: "", check: "", params: "{}", severity: "warn", publication: "", section: "", quote: "" };

function draftOf(rule: DesignRule): Draft {
  return {
    id: rule.id,
    check: rule.check,
    params: JSON.stringify(rule.params, null, 2),
    severity: rule.severity,
    publication: rule.source?.publication ?? "",
    section: rule.source?.section ?? "",
    quote: rule.source?.quote ?? "",
  };
}

/** Design rules over the checked-in table, and the open TODO(user) items (dev-panel-insights). */
export default function Rules() {
  const queryClient = useQueryClient();
  const rules = useQuery({ queryKey: ["admin-rules"], queryFn: api.designRules });
  const items = useQuery({ queryKey: ["admin-open-items"], queryFn: api.openItems });
  const sources = useQuery({ queryKey: ["admin-guidelines"], queryFn: api.guidelineSources });
  const notes = useQuery({ queryKey: ["guideline-notes"], queryFn: api.guidelineNotes });
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const saved = (payload: DesignRulesPayload) => {
    setError(null);
    setDraft(EMPTY);
    queryClient.setQueryData(["admin-rules"], payload);
  };
  const save = useMutation({ mutationFn: api.saveDesignRule, onSuccess: saved, onError: (e: Error) => setError(e.message) });
  const reset = useMutation({ mutationFn: api.resetDesignRule, onSuccess: saved, onError: (e: Error) => setError(e.message) });

  if (!rules.data) return <Page>Loading…</Page>;
  const checks = rules.data.checks;
  const set = (field: keyof Draft) => (event: { target: { value: string } }) =>
    setDraft({ ...draft, [field]: event.target.value });

  return (
    <Page>
      <h1>Design rules</h1>
      <p className="text-sm text-muted-foreground">
        Every rule cites its source. Rules added or edited here apply from the next check, without a restart; the
        checked-in table is never rewritten.
      </p>
      {rules.data.rules.map((rule) => (
        <section key={rule.id} className={cardClass}>
          <h2>
            {rule.id} <span className="text-sm font-normal text-muted-foreground">({ORIGIN[rule.origin]})</span>
          </h2>
          {!rule.valid && <p className="text-sm text-destructive">Not in force: {rule.problem}</p>}
          <p>
            {rule.check} · {rule.severity} · {rule.applies_to}
          </p>
          <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(rule.params)}</pre>
          {rule.source && (
            <p className="text-sm">
              {rule.source.publication}, {rule.source.section}: “{rule.source.quote}”
            </p>
          )}
          <p className="space-x-2">
            <Button type="button" variant="outline" onClick={() => setDraft(draftOf(rule))}>
              Edit
            </Button>
            {rule.origin !== "file" && (
              <Button type="button" variant="outline" onClick={() => reset.mutate(rule.id)}>
                {rule.origin === "edited" ? "Reset to the file" : "Delete"}
              </Button>
            )}
          </p>
        </section>
      ))}

      <form
        className={cardClass}
        onSubmit={(event) => {
          event.preventDefault();
          let params: Record<string, unknown>;
          try {
            params = JSON.parse(draft.params || "{}");
          } catch {
            setError("Parameters must be JSON, e.g. {\"table\": [{\"thickness_mm\": 18, \"max_span_mm\": 800}]}.");
            return;
          }
          const check = checks.find((entry) => entry.name === draft.check);
          save.mutate({
            id: draft.id,
            check: draft.check,
            applies_to: check?.applies_to ?? "piece",
            params,
            severity: draft.severity,
            source: { publication: draft.publication, section: draft.section, quote: draft.quote },
          });
        }}
      >
        <h2>{rules.data.rules.some((rule) => rule.id === draft.id) ? `Edit ${draft.id}` : "Add a rule"}</h2>
        <Label htmlFor="rule-id">Id</Label>
        <Input id="rule-id" value={draft.id} onChange={set("id")} required />
        <Label htmlFor="rule-check">Check</Label>
        <Select id="rule-check" value={draft.check} onChange={set("check")} required>
          <option value="">Choose a check</option>
          {checks.map((check) => (
            <option key={check.name} value={check.name}>
              {check.name} ({check.applies_to})
            </option>
          ))}
        </Select>
        <Label htmlFor="rule-params">Parameters (JSON)</Label>
        <textarea
          id="rule-params"
          className="w-full rounded-md border px-3 py-2 font-mono text-sm"
          rows={4}
          value={draft.params}
          onChange={set("params")}
        />
        <Label htmlFor="rule-severity">Severity</Label>
        <Select id="rule-severity" value={draft.severity} onChange={set("severity")}>
          <option value="warn">warn</option>
          <option value="refuse">refuse</option>
        </Select>
        <Label htmlFor="rule-publication">Source</Label>
        <Select id="rule-publication" value={draft.publication} onChange={set("publication")} required>
          <option value="">Choose a publication or one of your notes</option>
          {(sources.data ?? [])
            .filter((source) => source.origin === "list")
            .map((source) => (
              <option key={source.id} value={source.id}>
                {source.title}
              </option>
            ))}
          {(notes.data ?? []).map((note) => (
            <option key={note.id} value={`owner:${note.id}`}>
              Your note: {note.title}
            </option>
          ))}
        </Select>
        <Label htmlFor="rule-section">Section</Label>
        <Input id="rule-section" value={draft.section} onChange={set("section")} required />
        <Label htmlFor="rule-quote">Quoted clause</Label>
        <Input id="rule-quote" value={draft.quote} onChange={set("quote")} required />
        <p className="space-x-2">
          <Button type="submit" disabled={save.isPending}>
            Save rule
          </Button>
          <Button type="button" variant="ghost" onClick={() => setDraft(EMPTY)}>
            Clear
          </Button>
        </p>
      </form>
      {error && <p className="text-sm text-destructive">{error}</p>}

      <h1>Open items for you</h1>
      <p className="text-sm text-muted-foreground">Every TODO(user) in the backend code and configuration.</p>
      <ul className="space-y-1">
        {(items.data ?? []).map((item) => (
          <li key={`${item.file}:${item.line}`}>
            <code>
              {item.file}:{item.line}
            </code>{" "}
            {item.text}
          </li>
        ))}
      </ul>
    </Page>
  );
}
