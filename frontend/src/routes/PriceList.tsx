import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, type PriceEntry } from "../lib/api";
import { FieldError, fieldError, formError } from "../lib/form";
import { euros, toCents } from "../lib/money";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";

const CATEGORIES = ["panel", "hardware", "finish", "edge_band", "cut_service", "delivery"];
const UNITS = ["per_m2", "per_piece", "per_metre", "per_cut"];

function AddEntryForm({ onDone }: { onDone: () => void }) {
  const [key, setKey] = useState("");
  const [label, setLabel] = useState("");
  const [category, setCategory] = useState("hardware");
  const [unit, setUnit] = useState("per_piece");
  const [price, setPrice] = useState("");
  const [sheet, setSheet] = useState({ length: "", width: "", thickness: "" });
  const [local, setLocal] = useState<string | null>(null);
  const add = useMutation({ mutationFn: api.createEntry, onSuccess: onDone });
  const fields = ["key", "label", "category", "unit", "base_cents", "sheet_length_mm", "sheet_width_mm", "thickness_mm"];

  function submit(event: FormEvent) {
    event.preventDefault();
    const cents = toCents(price);
    if (cents === null) return setLocal("Enter the price as euros, for example 12,50.");
    setLocal(null);
    add.mutate({
      key, label, category, unit, base_cents: cents,
      ...(category === "panel"
        ? { sheet_length_mm: Number(sheet.length), sheet_width_mm: Number(sheet.width), thickness_mm: Number(sheet.thickness) }
        : {}),
    });
  }

  return (
    <form onSubmit={submit} className={cardClass} aria-label="Add an entry">
      <h2>Add an entry</h2>
      <Label htmlFor="add-key">Key</Label>
      <Input id="add-key" value={key} onChange={(e) => setKey(e.target.value)} />
      <FieldError message={fieldError(add.error, "key")} />
      <Label htmlFor="add-label">Label</Label>
      <Input id="add-label" value={label} onChange={(e) => setLabel(e.target.value)} />
      <FieldError message={fieldError(add.error, "label")} />
      <Label htmlFor="add-category">Category</Label>
      <Select id="add-category" value={category} onChange={(e) => setCategory(e.target.value)}>
        {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
      </Select>
      <Label htmlFor="add-unit">Unit</Label>
      <Select id="add-unit" value={unit} onChange={(e) => setUnit(e.target.value)}>
        {UNITS.map((u) => <option key={u}>{u}</option>)}
      </Select>
      <Label htmlFor="add-price">Price (€)</Label>
      <Input id="add-price" value={price} onChange={(e) => setPrice(e.target.value)} />
      <FieldError message={local ?? fieldError(add.error, "base_cents")} />
      {category === "panel" && (
        <>
          <Label htmlFor="add-sheet-length">Sheet length (mm)</Label>
          <Input id="add-sheet-length" value={sheet.length} onChange={(e) => setSheet({ ...sheet, length: e.target.value })} />
          <FieldError message={fieldError(add.error, "sheet_length_mm")} />
          <Label htmlFor="add-sheet-width">Sheet width (mm)</Label>
          <Input id="add-sheet-width" value={sheet.width} onChange={(e) => setSheet({ ...sheet, width: e.target.value })} />
          <FieldError message={fieldError(add.error, "sheet_width_mm")} />
          <Label htmlFor="add-thickness">Thickness (mm)</Label>
          <Input id="add-thickness" value={sheet.thickness} onChange={(e) => setSheet({ ...sheet, thickness: e.target.value })} />
          <FieldError message={fieldError(add.error, "thickness_mm")} />
        </>
      )}
      <FieldError message={formError(add.error, fields)} />
      <p><Button type="submit">Add</Button></p>
    </form>
  );
}

function FromUrlForm({ onDone }: { onDone: () => void }) {
  const [url, setUrl] = useState("");
  const [key, setKey] = useState("");
  const [category, setCategory] = useState("panel");
  const create = useMutation({ mutationFn: api.entryFromUrl, onSuccess: onDone });

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate({ url, key, category });
  }

  return (
    <form onSubmit={submit} className={cardClass} aria-label="Paste a toom URL">
      <h2>Paste a toom URL</h2>
      <Label htmlFor="url">toom product URL</Label>
      <Input id="url" value={url} onChange={(e) => setUrl(e.target.value)} />
      <Label htmlFor="url-key">Key</Label>
      <Input id="url-key" value={key} onChange={(e) => setKey(e.target.value)} />
      <FieldError message={fieldError(create.error, "key")} />
      <Label htmlFor="url-category">Category</Label>
      <Select id="url-category" value={category} onChange={(e) => setCategory(e.target.value)}>
        {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
      </Select>
      <FieldError message={formError(create.error, ["key"])} />
      <p>
        <Button type="submit" disabled={create.isPending}>Create from URL</Button>
        {create.isPending && <> <span role="status">Reading the page…</span></>}
      </p>
    </form>
  );
}

function EntryRow({ entry, onChange }: { entry: PriceEntry; onChange: () => void }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(entry.label);
  const [price, setPrice] = useState(entry.base_cents === null ? "" : String(entry.base_cents / 100));
  const [override, setOverride] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const edit = useMutation({
    mutationFn: () => api.editEntry(entry.key, { label, ...(toCents(price) === null ? {} : { base_cents: toCents(price)! }) }),
    onSuccess: () => { setEditing(false); onChange(); },
  });
  const set = useMutation({
    mutationFn: () => api.setOverride(entry.key, toCents(override) ?? -1, note || null),
    onSuccess: () => { setOverride(""); setNote(""); onChange(); },
  });
  const clear = useMutation({ mutationFn: () => api.clearOverride(entry.key), onSuccess: onChange });
  const refresh = useMutation({
    mutationFn: () => api.refreshEntry(entry.key),
    onSuccess: (result) => {
      setMessage(result.outcome === "ok" ? "Refreshed." : `Not refreshed (${result.outcome}): ${result.reason ?? ""}`);
      onChange();
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : "Refresh failed."),
  });
  const error = edit.error ?? set.error ?? clear.error;

  return (
    <TableRow>
      <TableCell>
        {editing ? <Input aria-label={`label of ${entry.key}`} value={label} onChange={(e) => setLabel(e.target.value)} /> : entry.label}
        <br /><small className="text-muted-foreground">{entry.key}</small>
      </TableCell>
      <TableCell>{entry.category}<br /><small className="text-muted-foreground">{entry.unit}</small></TableCell>
      <TableCell>
        <strong>{euros(entry.effective_cents)}</strong>
        {entry.unconfirmed && <><br /><small className="text-muted-foreground">unconfirmed</small></>}
        {entry.override_cents !== null && (
          <><br /><small className="text-muted-foreground">override {euros(entry.override_cents)}{entry.override_note ? ` — ${entry.override_note}` : ""}; captured {euros(entry.base_cents)}{entry.captured_at ? ` on ${entry.captured_at.slice(0, 10)}` : ""}</small></>
        )}
        {entry.override_cents === null && entry.captured_at && <><br /><small className="text-muted-foreground">captured {entry.captured_at.slice(0, 10)}</small></>}
      </TableCell>
      <TableCell><Badge variant="secondary">{entry.provenance}</Badge></TableCell>
      <TableCell className="min-w-72 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          {editing ? (
            <>
              <Input className="w-24" aria-label={`price of ${entry.key}`} value={price} onChange={(e) => setPrice(e.target.value)} />
              <Button size="sm" onClick={() => edit.mutate()}>Save</Button>
              <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
            </>
          ) : (
            <Button variant="outline" size="sm" aria-label={`Edit ${entry.key}`} onClick={() => setEditing(true)}>Edit</Button>
          )}
          {entry.provenance === "captured" && (
            <Button variant="outline" size="sm" aria-label={`Refresh ${entry.key}`} disabled={refresh.isPending} onClick={() => refresh.mutate()}>
              Refresh
            </Button>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Input className="w-24" aria-label={`override for ${entry.key}`} placeholder="override €" value={override} onChange={(e) => setOverride(e.target.value)} />
          <Input className="w-28" aria-label={`override note for ${entry.key}`} placeholder="note" value={note} onChange={(e) => setNote(e.target.value)} />
          <Button variant="secondary" size="sm" aria-label={`Set override on ${entry.key}`} onClick={() => set.mutate()}>Set</Button>
          {entry.override_cents !== null && (
            <Button variant="ghost" size="sm" aria-label={`Clear override on ${entry.key}`} onClick={() => clear.mutate()}>Clear</Button>
          )}
        </div>
        {refresh.isPending && <p role="status">Reading the page…</p>}
        {message && <p role="status">{message}</p>}
        {error && <p className="text-sm text-destructive" role="alert">{error instanceof Error ? error.message : "that did not work"}</p>}
      </TableCell>
    </TableRow>
  );
}

export default function PriceList() {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState("");
  const entries = useQuery({ queryKey: ["price-list", category], queryFn: () => api.priceList(category || undefined) });
  const reload = () => queryClient.invalidateQueries({ queryKey: ["price-list"] });

  return (
    <Page>
      <h1>Price list</h1>
      <Label htmlFor="filter">Category</Label>
      <Select id="filter" value={category} onChange={(e) => setCategory(e.target.value)}>
        <option value="">all</option>
        {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
      </Select>
      {entries.error && <p className="text-sm text-destructive" role="alert">The price list could not be loaded.</p>}
      <Table>
        <TableHeader>
          <TableRow><TableHead>Item</TableHead><TableHead>Category</TableHead><TableHead>Price</TableHead><TableHead>Source</TableHead><TableHead /></TableRow>
        </TableHeader>
        <TableBody>
          {(entries.data ?? []).map((entry) => <EntryRow key={entry.key} entry={entry} onChange={reload} />)}
        </TableBody>
      </Table>
      <AddEntryForm onDone={reload} />
      <FromUrlForm onDone={reload} />
    </Page>
  );
}
