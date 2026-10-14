import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type FeedbackRow } from "../../lib/api";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const name = (row: FeedbackRow) => `${row.slot ?? "no agent"} · ${row.model ?? "no model"} · ${row.tier}`;

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
    </>
  );
}
