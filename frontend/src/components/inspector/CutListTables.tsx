import { useState } from "react";
import type { DrillEntry, DrillingList, PieceSpec, SpecHardware, SpecPart } from "@/lib/api";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

/**
 * A built version's cut list and hardware, row for row from its `spec.json`
 * (piece-inspector) — the same document its `cutlist.csv` is written from.
 * Ported from the predecessor's `CutListPanel`, with its filter by module and
 * without the uploaded-list label. A module is named as the version's own
 * `module_names` names it. When a baseline version is given, new and changed
 * rows are highlighted in red (revision-confirm-highlight-cuts).
 */

/** The modules the parts name, in the order they first name them. */
function modulesOf(parts: SpecPart[]): string[] {
  const seen: string[] = [];
  for (const part of parts) {
    if (part.module && !seen.includes(part.module)) seen.push(part.module);
  }
  return seen;
}

/** Part and hardware ids that are new or changed against a baseline `spec.json`. */
export function changedCutIds(
  current: Pick<PieceSpec, "parts" | "hardware">,
  baseline: Pick<PieceSpec, "parts" | "hardware"> | null | undefined,
): { parts: Set<string>; hardware: Set<string> } {
  const parts = new Set<string>();
  const hardware = new Set<string>();
  if (!baseline) return { parts, hardware };
  const wasParts = new Map((baseline.parts ?? []).map((part) => [part.id, part]));
  for (const part of current.parts ?? []) {
    const before = wasParts.get(part.id);
    if (
      before === undefined ||
      before.l !== part.l ||
      before.w !== part.w ||
      before.t !== part.t ||
      before.qty !== part.qty
    ) {
      parts.add(part.id);
    }
  }
  const wasHardware = new Map((baseline.hardware ?? []).map((item) => [item.id, item]));
  for (const item of current.hardware ?? []) {
    const before = wasHardware.get(item.id);
    if (before === undefined || before.qty !== item.qty) hardware.add(item.id);
  }
  return { parts, hardware };
}

/**
 * The mark beside a hardware item the model does not fully show (hardware-catalog): `*` when fewer
 * pieces are drawn than the line counts, or when nothing is drawn of a line without a quantity, with
 * "(n of m shown)" when some are. A version built before `shown` existed is never marked.
 */
export function notShownMark(item: SpecHardware): string | null {
  if (item.shown === undefined) return null;
  if (item.qty === "") return item.shown === 0 ? "*" : null;
  if (item.shown >= item.qty) return null;
  return item.shown > 0 ? `* (${item.shown} of ${item.qty} shown)` : "*";
}

function rowClass(changed: boolean): string | undefined {
  return changed ? "text-destructive" : undefined;
}

function count(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

export function moduleLabel(spec: Pick<PieceSpec, "module_names">, module: string): string {
  return spec.module_names?.[module] ?? (module === "extras" ? "Extra parts" : module);
}

/** The line of one drilling entry without its part, which has its own column. */
function drillingText(entry: DrillEntry): string {
  const prefix = `${entry.part}: `;
  return entry.text.startsWith(prefix) ? entry.text.slice(prefix.length) : entry.text;
}

function workCounts(counts: DrillingList["counts"]): string {
  const work = [`${counts.hinge_cup_borings ?? 0} hinge cup borings`];
  if ("shelf_pin_holes" in counts) {
    work.push(counts.shelf_pin_holes === null ? "shelf-pin holes not counted" : `${counts.shelf_pin_holes} shelf-pin holes`);
  }
  return work.join(", ");
}

function DrillingTable({ drilling }: { drilling: DrillingList | undefined }) {
  if (!drilling) {
    return <p className="text-sm text-muted-foreground">Drilling was not calculated for this version.</p>;
  }
  return (
    <>
      {drilling.entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">This version has nothing to drill.</p>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Part</TableHead>
                <TableHead>Drilling</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {drilling.entries.map((entry, index) => (
                <TableRow key={`${entry.part}-${entry.what}-${index}`}>
                  <TableCell className="font-mono text-xs">{entry.part}</TableCell>
                  <TableCell className="text-sm">{drillingText(entry)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <p className="text-sm text-muted-foreground">Drilling work: {workCounts(drilling.counts)}.</p>
    </>
  );
}

export function CutListTables({
  spec,
  baseline,
}: {
  spec: PieceSpec;
  /** The revised-from version's `spec.json`; when absent every row stays normal. */
  baseline?: PieceSpec | null;
}) {
  const allParts = spec.parts ?? [];
  const hardware = spec.hardware ?? [];
  const modules = modulesOf(allParts);
  const [module, setModule] = useState<string | null>(null);
  const parts = module === null ? allParts : allParts.filter((part) => part.module === module);
  const pieces = parts.reduce((total, part) => total + part.qty, 0);
  const changed = changedCutIds(spec, baseline);
  return (
    <div className="grid gap-6">
      {spec.drilling && !spec.drilling.complete && (
        <Alert variant="destructive">
          <strong>The drilling list is incomplete.</strong>
          <ul className="mt-1 list-disc pl-5">
            {spec.drilling.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </Alert>
      )}
      <section aria-label="Cut list" className="grid gap-2">
        <h2>Cut list</h2>
        {allParts.length === 0 ? (
          <p className="text-sm text-muted-foreground">This version lists no parts.</p>
        ) : (
          <>
            {modules.length > 1 && (
              <div className="flex flex-wrap gap-1" role="group" aria-label="Filter by module">
                {[null, ...modules].map((candidate) => (
                  <Button
                    key={candidate ?? "all"}
                    type="button"
                    size="sm"
                    variant={candidate === module ? "default" : "outline"}
                    aria-pressed={candidate === module}
                    onClick={() => setModule(candidate)}
                  >
                    {candidate === null ? "All" : moduleLabel(spec, candidate)}
                  </Button>
                ))}
              </div>
            )}
            <p className="text-sm text-muted-foreground">
              {module === null ? "" : `${moduleLabel(spec, module)}: `}
              {count(parts.length, "part")}, {count(pieces, "piece")}. All dimensions in {spec.units ?? "mm"}.
            </p>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Part</TableHead>
                    <TableHead>Qty</TableHead>
                    <TableHead>L</TableHead>
                    <TableHead>W</TableHead>
                    <TableHead>T</TableHead>
                    <TableHead>Material</TableHead>
                    <TableHead>Grain</TableHead>
                    <TableHead>Banding</TableHead>
                    <TableHead>Module</TableHead>
                    <TableHead>Notes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {parts.map((part) => {
                    const highlight = changed.parts.has(part.id);
                    return (
                      <TableRow
                        key={part.id}
                        className={rowClass(highlight)}
                        data-changed={highlight || undefined}
                      >
                        <TableCell className="font-mono text-xs">{part.id}</TableCell>
                        <TableCell>{part.name}</TableCell>
                        <TableCell className="tabular-nums">{part.qty}</TableCell>
                        <TableCell className="tabular-nums">{part.l}</TableCell>
                        <TableCell className="tabular-nums">{part.w}</TableCell>
                        <TableCell className="tabular-nums">{part.t}</TableCell>
                        <TableCell>{part.material}</TableCell>
                        <TableCell>{part.grain}</TableCell>
                        <TableCell>{part.banding}</TableCell>
                        <TableCell title={part.module}>{moduleLabel(spec, part.module)}</TableCell>
                        <TableCell className={cn("text-xs", highlight ? undefined : "text-muted-foreground")}>
                          {part.notes}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </>
        )}
      </section>
      <section aria-label="Hardware" className="grid gap-2">
        <h2>Hardware</h2>
        {hardware.length === 0 ? (
          <p className="text-sm text-muted-foreground">This version lists no hardware.</p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Item</TableHead>
                  <TableHead>Qty</TableHead>
                  <TableHead>Notes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {hardware.map((item: SpecHardware) => {
                  const highlight = changed.hardware.has(item.id);
                  return (
                    <TableRow
                      key={item.id}
                      className={rowClass(highlight)}
                      data-changed={highlight || undefined}
                    >
                      <TableCell className="font-mono text-xs">{item.id}</TableCell>
                      <TableCell>
                        {item.item}
                        {notShownMark(item) && <span className="ml-1 text-muted-foreground">{notShownMark(item)}</span>}
                      </TableCell>
                      <TableCell className="tabular-nums">{item.qty === "" ? "no quantity" : item.qty}</TableCell>
                      <TableCell className={cn("text-xs", highlight ? undefined : "text-muted-foreground")}>
                        {item.notes}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
        {hardware.some((item) => notShownMark(item) !== null) && (
          <p className="text-sm text-muted-foreground">* not shown in the model</p>
        )}
      </section>
      <section aria-label="Drilling" className="grid gap-2">
        <h2>Drilling</h2>
        <DrillingTable drilling={spec.drilling} />
      </section>
    </div>
  );
}
