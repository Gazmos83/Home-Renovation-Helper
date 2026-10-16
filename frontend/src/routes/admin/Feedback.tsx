import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type FeedbackRow, type VerdictRow } from "../../lib/api";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const name = (row: FeedbackRow) => `${row.slot ?? "no agent"} · ${row.model ?? "no model"} · ${row.tier}`;
const verdictName = (row: VerdictRow) => `${row.slot ?? "no agent"} · ${row.model ?? "no model"}`;

export default function Feedback() {
  const summary = useQuery({ queryKey: ["admin-feedback"], queryFn: () => api.feedbackSummary(30) });
  const [selected, setSelected] = useState<FeedbackRow | null>(null);
  const comments = useQuery({
    queryKey: ["admin-feedback-comments", selected?.slot, selected?.model, selected?.tier],
    queryFn: () => api.feedbackComments(selected!),
    enabled: selected !== null,
  });
  if (!summary.data) return <>Loading…</>;
  return (
    <>
      <p>Ratings of renders in the last 30 days, per agent, model and tier. This never changes routing.</p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Agent</TableHead>
            <TableHead>Model</TableHead>
            <TableHead>Tier</TableHead>
            <TableHead>Up</TableHead>
            <TableHead>Down</TableHead>
            <TableHead>Comments</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {summary.data.map((row) => (
            <TableRow key={name(row)}>
              <TableCell>{row.slot ?? "—"}</TableCell>
              <TableCell>{row.model ?? "—"}</TableCell>
              <TableCell>{row.tier}</TableCell>
              <TableCell>{row.up}</TableCell>
              <TableCell>{row.down}</TableCell>
              <TableCell>
                <Button type="button" size="sm" variant="outline" onClick={() => setSelected(row)}>
                  Show comments for {name(row)}
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {summary.data.length === 0 && <p>No ratings yet.</p>}
      {selected && (
        <section aria-label="Comments">
          <h2>Comments: {name(selected)}</h2>
          {comments.data?.length === 0 && <p>No comments in this group.</p>}
          <ul>
            {(comments.data ?? []).map((c) => (
              <li key={c.at + c.render_key}>
                {c.rating === "up" ? "👍" : "👎"} {c.package_id} v{c.version} {c.render_key}: {c.comment}
              </li>
            ))}
          </ul>
        </section>
      )}
      <VersionVerdicts />
    </>
  );
}

/** version-verdict: "matches / doesn't match" per agent and model that made the version. */
function VersionVerdicts() {
  const summary = useQuery({ queryKey: ["admin-verdicts"], queryFn: () => api.verdictSummary(30) });
  const [selected, setSelected] = useState<VerdictRow | null>(null);
  const notes = useQuery({
    queryKey: ["admin-verdict-notes", selected?.slot, selected?.model],
    queryFn: () => api.verdictNotes(selected!),
    enabled: selected !== null,
  });
  if (!summary.data) return null;
  return (
    <section aria-label="Version verdicts" className="grid gap-2">
      <h2>Version verdicts</h2>
      <p>
        The owner's verdicts in the last 30 days on whether a version matches what they confirmed, per agent and
        model that made the version. Versions made before this was recorded count under no agent. This never changes
        routing.
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Agent</TableHead>
            <TableHead>Model</TableHead>
            <TableHead>Matches</TableHead>
            <TableHead>Doesn't match</TableHead>
            <TableHead>Notes</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {summary.data.map((row) => (
            <TableRow key={verdictName(row)}>
              <TableCell>{row.slot ?? "—"}</TableCell>
              <TableCell>{row.model ?? "—"}</TableCell>
              <TableCell>{row.matches}</TableCell>
              <TableCell>{row.mismatch}</TableCell>
              <TableCell>
                <Button type="button" size="sm" variant="outline" onClick={() => setSelected(row)}>
                  Show verdict notes for {verdictName(row)}
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {summary.data.length === 0 && <p>No verdicts yet.</p>}
      {selected && (
        <section aria-label="Verdict notes">
          <h3>Verdict notes: {verdictName(selected)}</h3>
          {notes.data?.length === 0 && <p>No notes in this group.</p>}
          <ul>
            {(notes.data ?? []).map((n) => (
              <li key={`${n.package_id}-${n.version}`}>
                {n.package_id} v{n.version} ({n.verdict === "matches" ? "matches" : `doesn't match, ${n.status}`}):{" "}
                {n.note}
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}
