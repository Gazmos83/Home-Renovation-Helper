import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, type KnowledgeSearch, type KnowledgeVersion } from "../../lib/api";
import { downloadJson } from "../../lib/download";
import { Page } from "@/components/Page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cardClass } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import EngineeringMethods from "./EngineeringMethods";

const json = (value: unknown) => JSON.stringify(value, null, 2);
const initialSource = json({ key: "", metadata: { title: "", publisher: null, source_url: null, edition: null, jurisdiction: null, standard_or_model: null, material_grade: null, thickness_mm: null }, collections: ["material_datasheets"] });
const sourceTemplate = json({ key: "lowercase-key-with-hyphens", metadata: { title: "", publisher: null, source_url: null, standard_or_model: null, edition: null, jurisdiction: null, language: null, source_kind: null, license_status: null, applicable_furniture: null, material_grade: null, thickness_mm: null, manufacturer: null, part_number: null, variant: null, page_section: null }, collections: ["material_datasheets"] });
const initialProperty = json({ block_id: "", kind: "E_MPa", original_unit: "MPa", original_value: null, original_minimum: null, original_maximum: null, value_basis: "unknown", standard_or_model: null, material_grade: null, thickness_mm: null, page_section: "", test_method: null, conditions: {} });

const whole = { pages: null, blocks: null };
const LOCAL = ["extraction", "local_embedding", "local_retrieval", "retention"];
const presets = [
  { label: "Local use", operations: LOCAL },
  { label: "Local use plus cloud excerpts", operations: [...LOCAL, "remote_model_use"] },
];
const pageSize = 10;
const views = [
  { id: "newest", label: "All, newest first" },
  { id: "alphabetical", label: "All, A–Z" },
  { id: "approved", label: "Approved only" },
  { id: "verified", label: "Verified only" },
];
const draftMarker = "[STATE YOUR BASIS HERE]";
const grantsFor = (operations: string[]) => json(Object.fromEntries(operations.map((name) => [name, whole])));
const draftEvidence = (version: KnowledgeVersion) => `DRAFT from catalogue metadata, edit before recording.\nSource: ${version.metadata.title}${version.metadata.edition ? `, edition ${version.metadata.edition}` : ""}.\nLink: ${version.metadata.source_url ?? "none"}\nLicence note: ${String(version.metadata.license_status ?? "none")}\nBasis for permission: ${draftMarker}`;

function JsonField({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (value: string) => void }) {
  return <><Label htmlFor={id}>{label}</Label><textarea id={id} className="w-full rounded-md border bg-background p-3 font-mono text-xs" rows={8} value={value} onChange={(event) => onChange(event.target.value)} /></>;
}

export default function Knowledge() {
  const cache = useQueryClient();
  const sources = useQuery({ queryKey: ["admin-knowledge"], queryFn: api.knowledgeSources });
  const [selected, setSelected] = useState("");
  const version = sources.data?.find((row) => row.id === selected);
  const catalogue = useQuery({ queryKey: ["admin-knowledge-catalogue"], queryFn: api.knowledgeCatalogue });
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!version) return;
    heading.current?.scrollIntoView?.({ block: "start" });
    heading.current?.focus();
  }, [version?.id]);
  const [source, setSource] = useState(initialSource);
  const [grants, setGrants] = useState("{}");
  const [rightsReviewer, setRightsReviewer] = useState("");
  const [rightsEvidence, setRightsEvidence] = useState("");
  const [expiry, setExpiry] = useState("");
  const [context, setContext] = useState("personal_home");
  const [reviewer, setReviewer] = useState("");
  const [preset, setPreset] = useState("");
  const [page, setPage] = useState(0);
  const [view, setView] = useState("newest");
  const listed = (sources.data ?? [])
    .filter((row) => view === "approved" ? row.rights_status === "approved" : view === "verified" ? row.verification_status === "verified" : true)
    .sort((a, b) => view === "alphabetical" ? a.metadata.title.localeCompare(b.metadata.title) || String(a.metadata.edition ?? "").localeCompare(String(b.metadata.edition ?? "")) : 0);
  const pages = Math.max(1, Math.ceil(listed.length / pageSize));
  const current = Math.min(page, pages - 1);
  const shown = listed.slice(current * pageSize, (current + 1) * pageSize);
  const technicalReviewer = reviewer || rightsReviewer;
  const [reviewStatus, setReviewStatus] = useState("needs_review");
  const [blocks, setBlocks] = useState("");
  const [property, setProperty] = useState(initialProperty);
  const [editing, setEditing] = useState("");
  const [replacement, setReplacement] = useState("");
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [filters, setFilters] = useState("{}");
  const [result, setResult] = useState<KnowledgeSearch | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [scope, setScope] = useState<string | null>(null);

  const feedback = (...where: string[]) => scope !== null && where.includes(scope) ? <>
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {notice && <p role="status">{notice}</p>}
  </> : null;

  async function run(action: () => Promise<unknown>, where: string | null = null) {
    setBusy(true); setError(null); setNotice(null); setScope(where);
    try { await action(); await cache.invalidateQueries({ queryKey: ["admin-knowledge"] }); await cache.invalidateQueries({ queryKey: ["admin-knowledge-catalogue"] }); }
    catch (error) { setError(error instanceof Error ? error.message : "Request failed"); }
    finally { setBusy(false); }
  }

  return <Page>
    <h1>Engineering knowledge</h1>
    <EngineeringMethods />
    <p>Register official links first. Rights approval, ingestion and technical review are separate steps. A reviewed property is evidence, not a calculated capacity or installation approval.</p>
    <div className="sticky top-0 z-10 bg-background">
      {busy && <p role="status">Working… large documents can take a few minutes.</p>}
      {((error && scope === null) || sources.error) && <p role="alert" className="text-destructive">{(scope === null ? error : null) ?? sources.error?.message}</p>}
      {notice && scope === null && <p role="status">{notice}</p>}
    </div>
    <details className={cardClass}><summary>Register a source version</summary>
      <form onSubmit={(event) => { event.preventDefault(); void run(async () => { const created = await api.registerKnowledge(JSON.parse(source)); setSelected(created.id); setNotice("Registered metadata only. No content downloaded or indexed."); }, "register"); }}>
        <p>Unknown fields remain null. All brief metadata fields are supported. Editions and identity remain immutable after registration; register another version for changed content.</p>
        <JsonField id="source-json" label="Source metadata and collections (JSON)" value={source} onChange={setSource} />
        <div className="flex flex-wrap items-center gap-3"><Button disabled={busy}>Register metadata only</Button><Button type="button" variant="outline" disabled={busy} onClick={() => setSource(sourceTemplate)}>Insert template</Button><Button type="button" variant="outline" onClick={() => downloadJson("engineering-source-template.json", JSON.parse(sourceTemplate))}>Export template</Button>{feedback("register")}</div>
      </form>
    </details>
    {catalogue.data && (catalogue.data.length > 0 || scope === "catalogue") && <details className={cardClass}><summary>Catalogue entries not yet registered ({catalogue.data.length})</summary>
      <p>Registering records metadata only: unverified, no rights, nothing downloaded.</p>
      <ul>{catalogue.data.map((entry) => <li key={entry.key} className="flex items-center gap-3">
        <span>{entry.metadata.title}{entry.metadata.edition ? ` (${entry.metadata.edition})` : ""}</span>
        <Button variant="outline" disabled={busy} onClick={() => void run(async () => { const created = await api.registerCatalogueEntry(entry.key); setSelected(created.id); setNotice("Registered metadata only. No content downloaded or indexed."); }, "catalogue")}>Register {entry.key}</Button>
      </li>)}</ul>{feedback("catalogue")}
    </details>}
    {sources.isPending && <p>Loading sources…</p>}
    {sources.data && <section className={`${cardClass} flex flex-wrap items-center justify-between gap-3`} aria-label="Source list controls">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Show sources">
        {views.map((item) => <Button key={item.id} type="button" size="sm" variant={view === item.id ? "default" : "outline"} aria-pressed={view === item.id} onClick={() => { setView(item.id); setPage(0); }}>{item.label}</Button>)}
      </div>
      <Badge variant="secondary">{listed.length} of {sources.data.length} sources</Badge>
    </section>}
    {sources.data && <Table><TableHeader><TableRow><TableHead>Source / edition</TableHead><TableHead>Content</TableHead><TableHead>Rights</TableHead><TableHead>Technical review</TableHead><TableHead /></TableRow></TableHeader><TableBody>
      {shown.map((row) => <TableRow key={row.id}>
        <TableCell>{row.metadata.title}<div className="text-xs text-muted-foreground">{row.metadata.edition ?? "Edition unknown"}</div></TableCell>
        <TableCell>{row.passages ? `${row.passages} blocks (${row.state})` : `Link-only / ${row.state}`}{row.superseded_by && " · superseded"}</TableCell>
        <TableCell><Badge variant={row.rights_status === "approved" ? "default" : "outline"}>{row.rights_status === "approved" ? "Rights approved" : "Rights pending / revoked / expired"}</Badge></TableCell>
        <TableCell><Badge variant={row.verification_status === "verified" ? "default" : "outline"}>{row.verification_status} {row.reviewed_by && `by ${row.reviewed_by}`}</Badge></TableCell>
        <TableCell><Button variant="outline" size="sm" onClick={() => { setSelected(row.id); setEditing(""); setProperty(initialProperty); setPreset(""); setGrants("{}"); setRightsEvidence(draftEvidence(row)); }}>Manage {row.metadata.title}</Button></TableCell>
      </TableRow>)}
    </TableBody></Table>}
    {sources.data && listed.length === 0 && <p className="text-sm text-muted-foreground">No sources match this view.</p>}
    {sources.data && pages > 1 && <nav aria-label="Source pages" className="flex items-center justify-between gap-3">
      <Button variant="outline" size="sm" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous page</Button>
      <span className="text-sm text-muted-foreground">Page {current + 1} of {pages} ({listed.length} sources)</span>
      <Button variant="outline" size="sm" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>Next page</Button>
    </nav>}
    {version && <section className="space-y-6" aria-label="Selected source">
      <h2 ref={heading} tabIndex={-1}>{version.metadata.title}</h2><p className="break-all text-xs">Version {version.id}</p>
      {version.metadata.source_url && <a href={version.metadata.source_url} target="_blank" rel="noreferrer">Official source link</a>}
      <details className={cardClass}><summary>Metadata, current grants and decision history</summary><pre className="overflow-auto text-xs">{json({ metadata: version.metadata, grants: version.grants, rights: version.rights, content_hash: version.content_hash })}</pre></details>
      <form className={cardClass} onSubmit={(event) => { event.preventDefault(); void run(() => api.knowledgeRights(version.id, { action: "approve", reviewer: rightsReviewer, evidence: rightsEvidence, grants: JSON.parse(grants), expires_at: expiry ? new Date(expiry).toISOString() : null, use_context: context }), "rights"); }}>
        <h3>Record a rights decision</h3>
        <p>Record documented permission for each operation: extraction, local_embedding, local_retrieval, remote_model_use, retention and commercial_use. A licence note or possession of a PDF does not grant permission. Each grant accepts physical pages and block IDs, with null meaning the complete version; extraction uses pages only. Cloud replies use only remotely permitted evidence.</p>
        <Label htmlFor="rights-reviewer">Rights reviewer</Label><Input id="rights-reviewer" required value={rightsReviewer} onChange={(e) => setRightsReviewer(e.target.value)} />
        <Label htmlFor="rights-evidence">Supporting rights evidence</Label><textarea id="rights-evidence" required className="w-full rounded-md border p-3" value={rightsEvidence} onChange={(e) => setRightsEvidence(e.target.value)} />
        <fieldset><legend>Grant preset (none selected; each lists exactly what it grants)</legend>
          {presets.map((item) => <label key={item.label} className="mb-1 block"><input type="radio" name="grant-preset" checked={preset === item.label} onChange={() => { setPreset(item.label); setGrants(grantsFor(item.operations)); }} /> {item.label}: {item.operations.join(", ")}</label>)}
        </fieldset>
        <JsonField id="rights-grants" label="Operation grants (JSON)" value={grants} onChange={(value) => { setPreset(""); setGrants(value); }} />
        <Label htmlFor="rights-expiry">Expiry (optional)</Label><Input id="rights-expiry" type="datetime-local" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
        <Label htmlFor="rights-context">Use context</Label><select id="rights-context" value={context} onChange={(e) => setContext(e.target.value)}><option value="personal_home">Personal home</option><option value="commercial">Commercial</option></select>
        <div className="flex flex-wrap gap-3"><Button disabled={busy || rightsEvidence.includes(draftMarker)}>Record approval</Button><Button type="button" variant="outline" disabled={busy || !rightsEvidence.trim() || rightsEvidence.includes(draftMarker) || !rightsReviewer.trim()} onClick={() => void run(() => api.knowledgeRights(version.id, { action: "revoke", evidence: rightsEvidence, reviewer: rightsReviewer }), "rights")}>Record revocation</Button>{feedback("rights")}</div>
      </form>
      <form className={cardClass} onSubmit={(event) => { event.preventDefault(); void run(() => api.reviewKnowledge(version.id, { reviewer: technicalReviewer, status: reviewStatus }), "review"); }}>
        <h3>Technical review</h3><Label htmlFor="technical-reviewer">Technical reviewer</Label><Input id="technical-reviewer" required value={technicalReviewer} onChange={(e) => setReviewer(e.target.value)} />
        <Label htmlFor="technical-status">Review status</Label><select id="technical-status" value={reviewStatus} onChange={(e) => setReviewStatus(e.target.value)}><option value="needs_review">Needs review</option><option value="unverified">Unverified</option><option value="verified">Verified source / property record</option></select>
        <p>This review does not change rights or verify a calculation. The reviewer and status above also apply to explicit property reviews below.</p><div className="flex flex-wrap items-center gap-3"><Button disabled={busy}>Record source review</Button>{feedback("review")}</div>
      </form>
      <form className={cardClass} onSubmit={(event) => { event.preventDefault(); const input = event.currentTarget.elements.namedItem("pdf") as HTMLInputElement; const file = input.files?.[0]; void run(async () => { if (!file) throw new Error("Choose a PDF."); if (file.size > 50 * 1024 * 1024) throw new Error("The browser PDF limit is 50 MB. Use reviewed local-file ingestion for larger authorised files."); await api.stageKnowledge(version.id, file); setNotice("PDF staged only; ingestion requires extraction rights."); }, "stage"); }}>
        <h3>Stage a PDF</h3><p>Up to 50 MB. Staging requires retention rights and does not extract or index content. Larger documents with an official link use Ingest from official link below; others use the confined local-file CLI.</p>
        <Label htmlFor="knowledge-pdf">Engineering PDF</Label><Input id="knowledge-pdf" name="pdf" type="file" accept="application/pdf" /><div className="flex flex-wrap items-center gap-3"><Button disabled={busy || !("retention" in version.grants) || !!version.local_path}>Stage PDF only</Button>
          {feedback("stage")}</div>
      </form>
      <form className={cardClass} onSubmit={(event) => { event.preventDefault(); void run(async () => { const run = await api.ingestKnowledge(version.id, blocks.trim() ? JSON.parse(blocks) : null); if (run.state !== "published") throw new Error(`Ingestion ${run.state}: ${run.reason ?? "review required"}`); setNotice(`Published ${run.blocks} authorised blocks.`); }, "ingest"); }}>
        <h3>Ingest or publish reviewed transcriptions</h3><p>Leave blank to parse the staged file or approved URL. Ambiguous tables, equations and scans need explicit reviewed blocks, including page/section, units, conditions and reviewer. Publication rechecks current rights.</p>
        <JsonField id="reviewed-blocks" label="Reviewed blocks (JSON array, optional)" value={blocks} onChange={setBlocks} /><Button disabled={busy || !("extraction" in version.grants)}>Run authorised ingestion</Button>
        <Button type="button" variant="outline" disabled={busy || !version.metadata.source_url || !!version.local_path || !LOCAL.every((name) => name in version.grants)} onClick={() => void run(async () => { const run = await api.ingestKnowledgeLink(version.id); if (run.state !== "published") throw new Error(`Ingestion ${run.state}: ${run.reason ?? "review required"}`); setNotice(`Published ${run.blocks} authorised blocks from the official link.`); }, "link")}>Ingest from official link</Button>
        {feedback("link", "ingest")}
      </form>
      <form className={cardClass} onSubmit={(event) => { event.preventDefault(); void run(() => editing ? api.editKnowledgeProperty(editing, JSON.parse(property)) : api.addKnowledgeProperty(version.id, JSON.parse(property)), "property"); }}>
        <h3>{editing ? "Edit unreviewed candidate" : "Add property candidate"}</h3><p>Original units, range, value basis, exact model/grade/thickness and test conditions travel together. Unknown is null. Creation and edits remain unverified. A reviewed record requires a new candidate to change its value.</p>
        <JsonField id="property-json" label="Property record (JSON)" value={property} onChange={setProperty} /><Button disabled={busy}>{editing ? "Save unreviewed candidate" : "Add unverified candidate"}</Button>
        {feedback("property")}
        {editing && <Button type="button" variant="outline" onClick={() => { setEditing(""); setProperty(initialProperty); }}>New candidate</Button>}
      </form>
      {version.properties.map((prop) => <article key={prop.id} className={cardClass}><p>{String(prop.kind)} · {prop.verification_status} {prop.reviewed_by && `by ${prop.reviewed_by}`}</p><pre className="overflow-auto text-xs">{json(prop)}</pre>
        {!prop.reviewed_by && <Button variant="outline" onClick={() => { const { id, verification_status, reviewed_by, ...record } = prop; void verification_status; void reviewed_by; setEditing(id); setProperty(json(record)); }}>Edit candidate</Button>}
        <Button disabled={busy || !technicalReviewer.trim()} onClick={() => void run(() => api.reviewKnowledgeProperty(prop.id, { reviewer: technicalReviewer, status: reviewStatus }), `property:${prop.id}`)}>Record property review</Button>
        {feedback(`property:${prop.id}`)}
      </article>)}
      <form className={cardClass} onSubmit={(event) => { event.preventDefault(); void run(() => api.supersedeKnowledge(version.id, replacement), "supersede"); }}><Label htmlFor="replacement">Published replacement version ID</Label><Input id="replacement" value={replacement} onChange={(e) => setReplacement(e.target.value)} required /><Button disabled={busy}>Supersede with published edition</Button>{feedback("supersede")}</form>
    </section>}
    <form className={cardClass} onSubmit={(event) => { event.preventDefault(); void run(async () => setResult(await api.previewKnowledge({ query: search, mode, filters: JSON.parse(filters) })), "search"); }}>
      <h2>Eligible local retrieval preview</h2><p>Local results can include evidence that is prohibited from cloud use. Metadata-only matches never support numerical claims. Exact applicability filters are applied before result limits.</p>
      <Label htmlFor="knowledge-query">Engineering query</Label><Input id="knowledge-query" required value={search} onChange={(e) => setSearch(e.target.value)} />
      <Label htmlFor="knowledge-mode">Search mode</Label><select id="knowledge-mode" value={mode} onChange={(e) => setMode(e.target.value)}><option value="hybrid">Hybrid</option><option value="vector">Vector</option><option value="keyword">Keyword</option></select>
      <JsonField id="knowledge-filters" label="Applicability filters (JSON)" value={filters} onChange={setFilters} /><div className="flex flex-wrap items-center gap-3"><Button disabled={busy}>Preview eligible evidence</Button>{feedback("search")}</div>
    </form>
    {result && <section aria-label="Retrieval results"><h2>Retrieval results</h2>{result.limitation && <p>{result.limitation}</p>}<h3>Eligible evidence ({result.evidence.length})</h3><pre className="overflow-auto text-xs">{json(result.evidence)}</pre><h3>Metadata only ({result.metadata_only.length})</h3><pre className="overflow-auto text-xs">{json(result.metadata_only)}</pre></section>}
  </Page>;
}
