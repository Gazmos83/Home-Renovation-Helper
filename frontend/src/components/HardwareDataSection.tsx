import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, type HardwareDataSheet, type HardwareKind, type NewHardwareDataSheet } from "@/lib/api";
import { FieldError, fieldError, formError } from "@/lib/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cardClass } from "@/components/ui/card";

/**
 * The cited drilling values of each hinge and shelf-pin item (hardware-drilling). A value is one
 * number ("35") or a range ("80–120"), as its source gives it; a blank value is missing, never
 * guessed, and the cut list says so. The pins per shelf is a count and takes one whole number.
 */

type FieldDef = { name: string; label: string; count?: boolean };

const FIELDS: Record<HardwareKind, FieldDef[]> = {
  hinge: [
    { name: "cup_diameter_mm", label: "Cup Ø" },
    { name: "cup_depth_mm", label: "Cup depth" },
    { name: "cup_edge_distance_mm", label: "Cup edge distance" },
    { name: "end_distance_mm", label: "End distance from the door ends" },
    { name: "plate_setback_mm", label: "Plate setback" },
    { name: "plate_hole_spacing_mm", label: "Plate hole spacing" },
  ],
  shelf_pin: [
    { name: "hole_diameter_mm", label: "Hole Ø" },
    { name: "hole_depth_mm", label: "Hole depth" },
    { name: "pitch_mm", label: "Pitch" },
    { name: "first_hole_mm", label: "First hole" },
    { name: "last_hole_mm", label: "Last hole" },
    { name: "front_setback_mm", label: "Front setback" },
    { name: "rear_setback_mm", label: "Rear setback" },
    { name: "pins_per_shelf", label: "Pins per shelf", count: true },
  ],
};

const KIND_LABEL: Record<HardwareKind, string> = { hinge: "Hinge", shelf_pin: "Shelf pin" };

const NUMBER = "(\\d+(?:[.,]\\d+)?)";
const RANGE = new RegExp(`^${NUMBER}\\s*[–—-]\\s*${NUMBER}$`);

function toNumber(text: string): number {
  return Number(text.replace(",", "."));
}

/** "35" is one value, "80–120" a range; blank is missing. A range is sent as a range even for a count, so the service names it. */
export function parseMeasure(text: string, count = false): unknown {
  const trimmed = text.trim();
  if (!trimmed) return undefined;
  const range = RANGE.exec(trimmed);
  if (range) return { min: toNumber(range[1]), max: toNumber(range[2]) };
  const number = toNumber(trimmed);
  if (Number.isNaN(number)) return { value: trimmed };
  return count ? number : { value: number };
}

/** A stored value as the owner types it back: "35", "80–120", or "" when missing. */
export function measureText(raw: unknown): string {
  if (raw === undefined || raw === null) return "";
  if (typeof raw === "number") return String(raw);
  const measure = raw as { value?: number; min?: number; max?: number };
  if (measure.value !== undefined) return String(measure.value);
  return `${measure.min}–${measure.max}`;
}

function parseCountTable(text: string): unknown {
  const rows = text.split(",").map((row) => row.trim()).filter(Boolean);
  if (rows.length === 0) return undefined;
  return rows.map((row) => {
    const [height, hinges] = row.split(":").map((part) => toNumber(part));
    return { max_height_mm: height, hinges };
  });
}

function countTableText(raw: unknown): string {
  if (!Array.isArray(raw)) return "";
  return raw.map((row: { max_height_mm: number; hinges: number }) => `${row.max_height_mm}:${row.hinges}`).join(", ");
}

const FORM_FIELDS = ["key", "kind", "maker", "model", "page_url", "datasheet_url", "citation", "values", "source_kind"];

function SheetForm({ sheet, onDone }: { sheet?: HardwareDataSheet; onDone: () => void }) {
  const [key, setKey] = useState(sheet?.key ?? "");
  const [kind, setKind] = useState<HardwareKind>(sheet?.kind ?? "hinge");
  const [maker, setMaker] = useState(sheet?.maker ?? "");
  const [model, setModel] = useState(sheet?.model ?? "");
  const [sourceKind, setSourceKind] = useState<"toom" | "manual">(sheet?.source_kind ?? "toom");
  const [pageUrl, setPageUrl] = useState(sheet?.page_url ?? "");
  const [datasheetUrl, setDatasheetUrl] = useState(sheet?.datasheet_url ?? "");
  const [citation, setCitation] = useState(sheet?.citation ?? "");
  const [values, setValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const field of [...FIELDS.hinge, ...FIELDS.shelf_pin]) initial[field.name] = measureText(sheet?.values[field.name]);
    initial.plate_item = typeof sheet?.values.plate_item === "string" ? sheet.values.plate_item : "";
    initial.count_table = countTableText(sheet?.values.count_table);
    return initial;
  });
  const id = sheet?.id ?? "new";

  const save = useMutation({
    mutationFn: (payload: NewHardwareDataSheet) => {
      if (!sheet) return api.createHardwareData(payload);
      const { key: _key, ...rest } = payload;
      return api.updateHardwareData(sheet.id, rest);
    },
    onSuccess: () => {
      if (!sheet) {
        setKey(""); setMaker(""); setModel(""); setPageUrl(""); setDatasheetUrl(""); setCitation(""); setValues({});
      }
      onDone();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const stated: Record<string, unknown> = {};
    for (const field of FIELDS[kind]) {
      const parsed = parseMeasure(values[field.name] ?? "", field.count);
      if (parsed !== undefined) stated[field.name] = parsed;
    }
    if (kind === "hinge") {
      const plate = (values.plate_item ?? "").trim();
      if (plate) stated.plate_item = plate;
      const table = parseCountTable(values.count_table ?? "");
      if (table !== undefined) stated.count_table = table;
    }
    save.mutate({
      key: key.trim(), kind, maker, model, values: stated, source_kind: sourceKind,
      page_url: pageUrl.trim() || null, datasheet_url: datasheetUrl.trim() || null, citation,
    });
  }

  const set = (name: string) => (event: { target: { value: string } }) =>
    setValues((current) => ({ ...current, [name]: event.target.value }));

  return (
    <form onSubmit={submit} className={cardClass} aria-label={sheet ? `Edit ${sheet.key}` : "Add hardware data"}>
      <h3>{sheet ? `Edit ${sheet.key}` : "Add hardware data"}</h3>
      {!sheet && (
        <>
          <Label htmlFor={`hw-key-${id}`}>Item key</Label>
          <Input id={`hw-key-${id}`} value={key} onChange={(e) => setKey(e.target.value)} />
          <FieldError message={fieldError(save.error, "key")} />
        </>
      )}
      <Label htmlFor={`hw-kind-${id}`}>Kind</Label>
      <Select id={`hw-kind-${id}`} value={kind} onChange={(e) => setKind(e.target.value as HardwareKind)}>
        <option value="hinge">Hinge</option>
        <option value="shelf_pin">Shelf pin</option>
      </Select>
      <Label htmlFor={`hw-maker-${id}`}>Maker</Label>
      <Input id={`hw-maker-${id}`} value={maker} onChange={(e) => setMaker(e.target.value)} />
      <FieldError message={fieldError(save.error, "maker")} />
      <Label htmlFor={`hw-model-${id}`}>Model</Label>
      <Input id={`hw-model-${id}`} value={model} onChange={(e) => setModel(e.target.value)} />
      <FieldError message={fieldError(save.error, "model")} />
      <Label htmlFor={`hw-source-${id}`}>Source</Label>
      <Select id={`hw-source-${id}`} value={sourceKind} onChange={(e) => setSourceKind(e.target.value as "toom" | "manual")}>
        <option value="toom">toom product page</option>
        <option value="manual">Data sheet entered by hand</option>
      </Select>
      <Label htmlFor={`hw-page-${id}`}>toom page URL</Label>
      <Input id={`hw-page-${id}`} value={pageUrl} onChange={(e) => setPageUrl(e.target.value)} />
      <FieldError message={fieldError(save.error, "page_url")} />
      <Label htmlFor={`hw-sheet-${id}`}>Maker's data sheet URL (optional)</Label>
      <Input id={`hw-sheet-${id}`} value={datasheetUrl} onChange={(e) => setDatasheetUrl(e.target.value)} />
      <Label htmlFor={`hw-citation-${id}`}>Data sheet citation</Label>
      <Input id={`hw-citation-${id}`} value={citation} onChange={(e) => setCitation(e.target.value)} />
      <FieldError message={fieldError(save.error, "citation")} />
      <p className="text-sm text-muted-foreground">
        Values in mm: one number (35) or a range (80–120), as the source gives it. Leave a value blank when the source does not state it.
      </p>
      {FIELDS[kind].map((field) => (
        <div key={field.name}>
          <Label htmlFor={`hw-${field.name}-${id}`}>{field.label}</Label>
          <Input id={`hw-${field.name}-${id}`} value={values[field.name] ?? ""} onChange={set(field.name)} />
        </div>
      ))}
      {kind === "hinge" && (
        <>
          <Label htmlFor={`hw-count-table-${id}`}>Hinges by door height (optional, "900:2, 1600:3")</Label>
          <Input id={`hw-count-table-${id}`} value={values.count_table ?? ""} onChange={set("count_table")} />
          <Label htmlFor={`hw-plate-item-${id}`}>Mounting plate item key (optional)</Label>
          <Input id={`hw-plate-item-${id}`} value={values.plate_item ?? ""} onChange={set("plate_item")} />
        </>
      )}
      <FieldError message={fieldError(save.error, "values")} />
      <FieldError message={formError(save.error, FORM_FIELDS)} />
      <p><Button type="submit">{sheet ? "Save data sheet" : "Add data sheet"}</Button></p>
    </form>
  );
}

function ValueList({ sheet }: { sheet: HardwareDataSheet }) {
  return (
    <ul className="grid gap-0.5 text-sm">
      {FIELDS[sheet.kind].map((field) => {
        const raw = sheet.values[field.name];
        const text = measureText(raw);
        const shown = text === "" ? null : field.count ? text : `${text} mm`;
        return (
          <li key={field.name}>
            {field.label}: {shown ?? <span className="text-destructive">missing</span>}
          </li>
        );
      })}
    </ul>
  );
}

export function HardwareDataSection() {
  const queryClient = useQueryClient();
  const sheets = useQuery({ queryKey: ["hardware-data"], queryFn: api.hardwareData });
  const [editing, setEditing] = useState<string | null>(null);
  const reload = () => queryClient.invalidateQueries({ queryKey: ["hardware-data"] });
  const remove = useMutation({ mutationFn: api.deleteHardwareData, onSuccess: reload });

  return (
    <section aria-label="Hardware data" className="grid gap-3">
      <h2>Hardware data</h2>
      <p>
        The drilling values of each hinge and shelf pin, from its toom page or its own data sheet. The cut list uses them to
        place holes; a value left blank is shown as missing, never guessed.
      </p>
      {(sheets.data ?? []).map((sheet) =>
        editing === sheet.id ? (
          <SheetForm key={sheet.id} sheet={sheet} onDone={() => { setEditing(null); reload(); }} />
        ) : (
          <section key={sheet.id} className={cardClass} aria-label={sheet.key}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <strong>{sheet.key}</strong> — {KIND_LABEL[sheet.kind]}, {sheet.maker} {sheet.model}
                <ValueList sheet={sheet} />
                <small className="text-muted-foreground">Source: {sheet.citation}</small>
              </div>
              <div>
                <Button variant="secondary" size="sm" onClick={() => setEditing(sheet.id)}>Edit {sheet.key}</Button>{" "}
                <Button variant="secondary" size="sm" onClick={() => remove.mutate(sheet.id)}>Delete {sheet.key}</Button>
              </div>
            </div>
          </section>
        ),
      )}
      <SheetForm onDone={reload} />
    </section>
  );
}
