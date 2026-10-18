import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type EngineeringReport, type ReadingEntry } from "@/lib/api";
import { FieldError } from "@/lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

function message(error: unknown): string | null {
  return error instanceof Error ? error.message : null;
}

/** "p. 3" or "pp. 3, 4", then the section, as the source states them. */
function where(pages: number[], section: string | null): string {
  const parts = [];
  if (pages.length) parts.push(`${pages.length > 1 ? "pp." : "p."} ${pages.join(", ")}`);
  if (section) parts.push(section);
  return parts.join(" · ");
}

/** A listed source's blocks, read on this machine, one page at a time. */
function SourceReader({ packageId, version, entry }: { packageId: string; version: number; entry: ReadingEntry }) {
  const [page, setPage] = useState(1);
  const blocks = useQuery({
    queryKey: ["reading-blocks", packageId, version, entry.version_id, page],
    queryFn: () => api.readingBlocks(packageId, version, entry.version_id, page),
  });
  if (blocks.error) return <FieldError message={message(blocks.error)} />;
  if (!blocks.data) return <p>Loading…</p>;
  if (!blocks.data.readable) return <p className="text-sm">Can't be read here: {blocks.data.reason}.</p>;
  return (
    <div className="grid gap-2 border-l pl-3">
      {blocks.data.blocks.map((block) => (
        <div key={block.block_id} className="grid gap-1">
          <p className="text-xs text-muted-foreground">{where(block.pages, block.section)}</p>
          <p className="whitespace-pre-wrap text-sm">{block.text}</p>
          {block.conditions.length > 0 && (
            <p className="text-xs text-muted-foreground">Conditions: {block.conditions.join("; ")}</p>
          )}
        </div>
      ))}
      <div className="flex gap-2">
        {page > 1 && (
          <Button variant="outline" size="sm" onClick={() => setPage(page - 1)}>
            Previous
          </Button>
        )}
        {blocks.data.more && (
          <Button variant="outline" size="sm" onClick={() => setPage(page + 1)}>
            Next
          </Button>
        )}
      </div>
    </div>
  );
}

function Entry({
  packageId,
  version,
  entry,
  itemId,
}: {
  packageId: string;
  version: number;
  entry: ReadingEntry;
  itemId: string;
}) {
  const [open, setOpen] = useState(false);
  const citation = [entry.publisher, entry.edition, entry.standard_or_model, entry.page_section, entry.jurisdiction];
  return (
    <li className="grid gap-1">
      <div className="flex flex-wrap items-center gap-2">
        {entry.source_url ? (
          <a href={entry.source_url} target="_blank" rel="noreferrer noopener" className="font-medium underline">
            {entry.title}
          </a>
        ) : (
          <span className="font-medium">{entry.title}</span>
        )}
        <Badge variant={entry.verification_status === "verified" ? "default" : "outline"}>
          {entry.verification_status === "verified" ? "verified" : "unverified"}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        Publisher: {citation[0]} · Edition: {citation[1]} · Standard or model: {citation[2]} · Page or section:{" "}
        {citation[3]} · Jurisdiction: {citation[4]}
      </p>
      <p className="text-xs text-muted-foreground">Matched by {entry.matched_by[itemId]}</p>
      <div>
        <Button variant="outline" size="sm" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Hide" : "Read here"}
        </Button>
      </div>
      {open && <SourceReader packageId={packageId} version={version} entry={entry} />}
    </li>
  );
}

function Report({ report }: { report: EngineeringReport }) {
  const evidence = Object.entries(report.snapshot?.evidence ?? {});
  return (
    <li className="grid gap-1">
      <p className="text-sm font-medium">
        Outcome: {report.overall} · Conformity not established
      </p>
      {report.stale && <p className="text-sm">Stale: {report.stale_reasons.join("; ")}</p>}
      {report.evidence_unavailable ? (
        <p className="text-sm">{report.limitation}</p>
      ) : (
        evidence.map(([id, item]) => (
          <div key={id} className="grid gap-1 border-l pl-3">
            <p className="text-xs text-muted-foreground">
              {item.packet.metadata.title ?? "Source"} · {where(item.packet.block.pages, item.packet.block.section)}
            </p>
            <p className="whitespace-pre-wrap text-sm">{item.packet.text}</p>
          </div>
        ))
      )}
    </li>
  );
}

/**
 * The inspector's Reading tab (installation-reading): recommended reading for the wall-hung
 * items of an approved version, matched by fixed rules, with each source readable here while
 * its rights allow, and the version's stored engineering reports. Nothing here reaches a model.
 */
export function ReadingTab({ packageId, version, approved }: { packageId: string; version: number; approved: boolean }) {
  const reading = useQuery({
    queryKey: ["reading", packageId, version],
    queryFn: () => api.reading(packageId, version),
    enabled: approved,
  });
  const reports = useQuery({
    queryKey: ["engineering-reports", packageId, version],
    queryFn: () => api.engineeringReports(packageId, version),
  });

  let list;
  if (!approved) list = <p>Approve this version to see recommended reading</p>;
  else if (reading.error) list = <FieldError message={message(reading.error)} />;
  else if (!reading.data) list = <p>Loading…</p>;
  else {
    const data = reading.data;
    list = (
      <div className="grid gap-3">
        <p role="note" className="rounded border p-2 text-sm">
          {data.notice}
        </p>
        {data.message && <p>{data.message}</p>}
        {data.items.map((item) => {
          const entries = data.entries.filter((entry) => entry.items.includes(item.id));
          const gap = data.gaps.find((g) => g.item === item.id);
          return (
            <section key={item.id} className="grid gap-2" aria-label={item.name}>
              <h3 className="font-medium">
                {item.name} ({item.kind === "wall_shelf" ? "wall shelf" : "wall-mounted module"})
              </h3>
              {gap && <p className="text-sm">{gap.reason}</p>}
              <ul className="grid gap-3">
                {entries.map((entry) => (
                  <Entry key={entry.version_id} packageId={packageId} version={version} entry={entry} itemId={item.id} />
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    );
  }

  let stored;
  if (reports.error) stored = <FieldError message={message(reports.error)} />;
  else if (!reports.data) stored = <p>Loading…</p>;
  else if (reports.data.length === 0) stored = <p>No engineering reports for this version.</p>;
  else
    stored = (
      <ul className="grid gap-3">
        {reports.data.map((report) => (
          <Report key={report.report_id} report={report} />
        ))}
      </ul>
    );

  return (
    <div className="grid gap-4">
      {list}
      <section className="grid gap-2" aria-label="Engineering reports">
        <h3 className="font-medium">Engineering reports</h3>
        {stored}
      </section>
    </div>
  );
}
