import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cardClass } from "@/components/ui/card";
import { GuidelineNotesSection } from "@/components/GuidelineNotesSection";
import { HardwareDataSection } from "@/components/HardwareDataSection";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

/**
 * The Design Knowledge tab's Guidelines view: guideline sources (the checked-in list and PDFs uploaded
 * here, each ingested into the corpus; dev-panel-insights), then the owner's notes and hardware data
 * (merge-guideline-pages).
 */
export default function Guidelines() {
  const queryClient = useQueryClient();
  const sources = useQuery({ queryKey: ["admin-guidelines"], queryFn: api.guidelineSources });
  const [error, setError] = useState<string | null>(null);
  const done = () => {
    setError(null);
    queryClient.invalidateQueries({ queryKey: ["admin-guidelines"] });
  };
  const fail = (failure: Error) => setError(failure.message);
  const upload = useMutation({ mutationFn: api.uploadGuideline, onSuccess: done, onError: fail });
  const reingest = useMutation({ mutationFn: api.reingestGuideline, onSuccess: done, onError: fail });
  const remove = useMutation({ mutationFn: api.deleteGuideline, onSuccess: done, onError: fail });

  return (
    <div className="space-y-6">
      <section aria-label="Guideline PDFs" className="grid gap-3">
        <h2>Guideline PDFs</h2>
        <form
          className={cardClass}
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            const input = event.currentTarget.elements.namedItem("file") as HTMLInputElement | null;
            const file = input?.files?.[0];
            if (!file || file.size === 0) {
              setError("Choose a PDF to upload.");
              return;
            }
            upload.mutate({
              file,
              title: String(form.get("title") ?? ""),
              jurisdiction: String(form.get("jurisdiction") ?? ""),
              published_on: String(form.get("published_on") ?? ""),
              licence: String(form.get("licence") ?? ""),
            });
          }}
        >
          <h3>Upload a PDF</h3>
          <Label htmlFor="guideline-file">PDF</Label>
          <Input id="guideline-file" name="file" type="file" accept="application/pdf" />
          <Label htmlFor="guideline-title">Title</Label>
          <Input id="guideline-title" name="title" required maxLength={200} />
          <Label htmlFor="guideline-jurisdiction">Jurisdiction</Label>
          <Input id="guideline-jurisdiction" name="jurisdiction" required maxLength={200} />
          <Label htmlFor="guideline-published">Published on</Label>
          <Input id="guideline-published" name="published_on" type="date" required />
          <Label htmlFor="guideline-licence">Licence note</Label>
          <Input id="guideline-licence" name="licence" required maxLength={2000} />
          <p>
            <Button type="submit" disabled={upload.isPending}>
              {upload.isPending ? "Uploading and ingesting…" : "Upload and ingest"}
            </Button>
          </p>
        </form>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {sources.data && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>From</TableHead>
                <TableHead>Published</TableHead>
                <TableHead>Passages</TableHead>
                <TableHead>State</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {sources.data.map((source) => (
                <TableRow key={source.id}>
                  <TableCell>
                    {source.title}
                    <div className="text-xs text-muted-foreground">{source.id}</div>
                  </TableCell>
                  <TableCell>{source.origin === "list" ? "checked-in list" : "uploaded"}</TableCell>
                  <TableCell>{source.published_on}</TableCell>
                  <TableCell>{source.passages}</TableCell>
                  <TableCell>
                    {source.error ? `failed: ${source.error}` : source.passages > 0 ? "ingested" : "not ingested"}
                  </TableCell>
                  <TableCell className="space-x-2">
                    {source.deletable && (
                      <>
                        <Button type="button" variant="outline" onClick={() => reingest.mutate(source.id)}>
                          Re-ingest
                        </Button>
                        <Button type="button" variant="destructive" onClick={() => remove.mutate(source.id)}>
                          Delete
                        </Button>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
      <GuidelineNotesSection />
      <HardwareDataSection />
    </div>
  );
}
