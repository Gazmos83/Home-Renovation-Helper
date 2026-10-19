import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, type EngineeringMethod } from "../../lib/api";
import { downloadJson } from "../../lib/download";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cardClass } from "@/components/ui/card";

/** A reviewer's worksheet. Methods are defined in reviewed code, so this file documents a proposal; it is never imported. */
const methodTemplate = (method?: EngineeringMethod) => ({
  purpose: "Reviewer package for one engineering calculation method. Not imported by the application: a method exists only as reviewed code and is enabled by the review action in the developer panel.",
  method_id: method?.id ?? "",
  method_version: method?.version ?? "1",
  domain: method?.domain ?? "",
  units: method?.units ?? [],
  required_inputs: method?.required_inputs ?? [],
  citations: (method?.citation_evidence_ids ?? [""]).map((id) => ({ evidence_id: id, title: "", clause_or_page: "" })),
  criteria: method?.criteria.length ? method.criteria : [{ id: "", limit: null, unit: "", source_evidence_id: "" }],
  independent_reference_cases: method?.independent_reference_cases.length ? method.independent_reference_cases : [{ inputs: {}, expected: {}, source: "", checked_by: "" }],
  supported_domain_limits: "",
  qualified_review: { reviewer: "", qualification_evidence: "", scope_evidence: "" },
  definition_hash: method?.definition_hash ?? null,
});

const readFile = (file: File) => new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new Error("The file could not be read.")); reader.readAsText(file); });
const reviewLimit = 4000;
/** Reads a filled worksheet into the review form. It checks the exact method and definition, and never records anything. */
function readWorksheet(text: string, method: EngineeringMethod) {
  let sheet: Record<string, unknown>;
  try { sheet = JSON.parse(text); } catch { throw new Error("The worksheet is not valid JSON."); }
  if (typeof sheet !== "object" || sheet === null || Array.isArray(sheet)) throw new Error("The worksheet must be a JSON object.");
  if (sheet.method_id !== method.id || sheet.method_version !== method.version) throw new Error(`This worksheet is for ${String(sheet.method_id) || "no method"} v${String(sheet.method_version)}, not ${method.id} v${method.version}.`);
  if (sheet.definition_hash && sheet.definition_hash !== method.definition_hash) throw new Error("The worksheet was exported from a different version of this method definition. Export a new package and carry the review across.");
  const review = (typeof sheet.qualified_review === "object" && sheet.qualified_review !== null ? sheet.qualified_review : {}) as Record<string, unknown>;
  const text_ = (value: unknown) => (typeof value === "string" ? value.trim() : "");
  const worksheet = JSON.stringify({ domain_limits: sheet.supported_domain_limits ?? "", citations: sheet.citations ?? [], criteria: sheet.criteria ?? [], independent_reference_cases: sheet.independent_reference_cases ?? [] });
  const evidence = [text_(review.scope_evidence), `Worksheet: ${worksheet}`].filter(Boolean).join("\n\n");
  if (evidence.length > reviewLimit || text_(review.qualification_evidence).length > reviewLimit) throw new Error(`The worksheet content is longer than the ${reviewLimit}-character review limit. Shorten the reference cases or keep them in the document and cite it.`);
  return { reviewer: text_(review.reviewer), qualifications: text_(review.qualification_evidence), evidence };
}

export default function EngineeringMethods() {
  const cache = useQueryClient();
  const methods = useQuery({ queryKey: ["engineering-methods"], queryFn: api.engineeringMethods });
  const [selected, setSelected] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [qualifications, setQualifications] = useState("");
  const [evidence, setEvidence] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const method = methods.data?.find((method) => method.id === selected);
  async function review(action: "pending" | "accept" | "disable") {
    if (!method) return;
    setBusy(true); setError(null);
    try {
      await api.reviewEngineeringMethod(method.id, { action, method_version: method.version, definition_hash: method.definition_hash, reviewer, qualification_evidence: qualifications, evidence });
      await cache.invalidateQueries({ queryKey: ["engineering-methods"] });
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Method review failed"); }
    finally { setBusy(false); }
  }
  async function importWorksheet(file: File | undefined) {
    if (!method || !file) return;
    setImportError(null); setNotice(null);
    try {
      const sheet = readWorksheet(await readFile(file), method);
      setReviewer(sheet.reviewer); setQualifications(sheet.qualifications); setEvidence(sheet.evidence);
      setNotice("Worksheet read into the review form. Nothing has been recorded; check the fields, then choose a review action.");
    } catch (failure) { setImportError(failure instanceof Error ? failure.message : "The worksheet could not be read."); }
    if (fileInput.current) fileInput.current.value = "";
  }
  return <section className={cardClass}>
    <h2>Engineering calculation methods</h2>
    <p>Methods require exact cited equations, criteria, independently checked reference cases and qualified review before enablement. A visual approval or source-rights approval cannot supply that review. Only a method with a complete source/review package in code (shown with no limitation below) can be accepted.</p>
    {(error || methods.error) && <p role="alert" className="text-destructive">{error ?? methods.error?.message}</p>}
    {methods.isPending && <p>Loading methods…</p>}
    <div><Button type="button" variant="outline" onClick={() => downloadJson("engineering-method-template.json", methodTemplate())}>Export blank method template</Button></div>
    <div className="flex flex-wrap gap-2">{methods.data?.map((item) => <Button key={item.id} variant="outline" onClick={() => setSelected(item.id)}>{item.id} · {item.enabled ? "enabled" : "unavailable"}</Button>)}</div>
    {method && <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); void review("pending"); }}>
      <h3>{method.id} v{method.version} · {method.qualified_review_state}</h3><p>{method.domain}</p><div className="flex flex-wrap items-center gap-3"><Button type="button" variant="outline" onClick={() => downloadJson(`${method.id}-v${method.version}-review-package.json`, methodTemplate(method))}>Export method package</Button>
        <Button type="button" variant="outline" onClick={() => fileInput.current?.click()}>Import worksheet</Button>
        <input ref={fileInput} type="file" accept="application/json,.json" className="hidden" aria-label="Method worksheet file" onChange={(event) => void importWorksheet(event.target.files?.[0])} />
        {importError && <p role="alert" className="text-destructive">{importError}</p>}
        {notice && <p role="status">{notice}</p>}</div>
      <p>{method.limitation}</p><pre className="overflow-auto text-xs">{JSON.stringify({ units: method.units, required_inputs: method.required_inputs, citations: method.citation_evidence_ids, criteria: method.criteria, references: method.independent_reference_cases, definition_hash: method.definition_hash }, null, 2)}</pre>
      <Label htmlFor="method-reviewer">Method reviewer</Label><Input id="method-reviewer" required value={reviewer} onChange={(event) => setReviewer(event.target.value)} />
      <Label htmlFor="method-qualifications">Qualified-review evidence</Label><Input id="method-qualifications" required value={qualifications} onChange={(event) => setQualifications(event.target.value)} />
      <Label htmlFor="method-evidence">Scope, criteria and reference review evidence</Label><textarea id="method-evidence" className="w-full rounded border p-3" required value={evidence} onChange={(event) => setEvidence(event.target.value)} />
      <div className="flex flex-wrap gap-3"><Button disabled={busy}>Record review pending</Button><Button type="button" disabled={busy || !method.releasable || !reviewer.trim() || !qualifications.trim() || !evidence.trim()} onClick={() => void review("accept")}>Accept qualified review and enable</Button><Button type="button" variant="outline" disabled={busy || !reviewer.trim() || !qualifications.trim() || !evidence.trim()} onClick={() => void review("disable")}>Disable method, retain history</Button></div>
    </form>}
  </section>;
}
