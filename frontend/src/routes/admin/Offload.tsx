import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type OffloadJob } from "../../lib/api";
import { FieldError, fieldError, formError } from "../../lib/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const seconds = (value: number | null) => (value === null ? "—" : `${value.toFixed(1)} s`);
const euros = (job: OffloadJob) => (job.cost_eur === null ? "—" : `€${job.cost_eur.toFixed(2)}`);

export default function Offload() {
  const queryClient = useQueryClient();
  const summary = useQuery({ queryKey: ["admin-offload"], queryFn: api.offload });
  const [rate, setRate] = useState<string | null>(null);
  const reload = () => queryClient.invalidateQueries({ queryKey: ["admin-offload"] });

  const test = useMutation({ mutationFn: api.testOffload });
  const benchmark = useMutation({ mutationFn: api.offloadBenchmark, onSuccess: reload });
  const target = useMutation({ mutationFn: api.setOffloadTarget, onSuccess: reload });
  const saveRate = useMutation({
    mutationFn: (value: number) => api.setOffloadRate(value),
    onSuccess: () => {
      setRate(null);
      reload();
    },
  });

  if (!summary.data) return <Page>Loading…</Page>;
  const data = summary.data;
  const shownRate = rate ?? (data.hourly_rate_eur === null ? "" : String(data.hourly_rate_eur));

  return (
    <Page>
      <h1>Render offload</h1>

      <section className={cardClass} aria-label="Render server">
        <h2>Render server</h2>
        {data.configured ? (
          <p>
            {data.user}@{data.host}:{data.port} · Blender at {data.blender} · {data.device}
          </p>
        ) : (
          <p>Not configured. Set the RENDER_OFFLOAD_* values (see the README); finals run on this laptop.</p>
        )}
        <p>
          <Button type="button" variant="outline" disabled={!data.configured} onClick={() => test.mutate()}>
            Test the connection
          </Button>
        </p>
        <FieldError message={formError(test.error, [])} />
        {test.data && (
          <p role="status">
            {test.data.reachable ? "Reachable" : "Not reachable"}
            {test.data.blender_version &&
              ` · Blender ${test.data.blender_version}${test.data.version_ok ? "" : ` (needs ${test.data.pinned_version})`}`}
            {test.data.gpus.length > 0 && ` · GPUs: ${test.data.gpus.join(", ")}`}
            {test.data.version_ok && test.data.gpus.length === 0 && " · no GPU listed"}
          </p>
        )}
      </section>

      <section className={cardClass} aria-label="Final target">
        <h2>Where finals run</h2>
        <Label htmlFor="final-target">Final renders</Label>
        <Select
          id="final-target"
          value={data.target}
          onChange={(event) => target.mutate(event.target.value as "local" | "remote")}
        >
          <option value="local">On this laptop</option>
          <option value="remote">On the render server</option>
        </Select>
        <FieldError message={fieldError(target.error, "target") ?? formError(target.error, ["target"])} />
        <p className="text-sm text-muted-foreground">
          Only finals can go to the server. If it is unreachable the render is refused; it never runs here instead.
        </p>
      </section>

      <section className={cardClass} aria-label="Remote benchmark">
        <h2>Remote benchmark</h2>
        {data.benchmark ? (
          <p>
            {data.benchmark.seconds_per_megapixel.toFixed(3)} s per megapixel + {data.benchmark.overhead_seconds.toFixed(0)} s
            overhead · measured {data.benchmark.measured_at.slice(0, 16).replace("T", " ")}
            {data.benchmark.calibrated ? " · calibrated by a final" : ""}
          </p>
        ) : (
          <p>Not measured yet. A remote final is refused until it is.</p>
        )}
        <p>
          <Button type="button" disabled={!data.configured || benchmark.isPending} onClick={() => benchmark.mutate()}>
            {benchmark.isPending ? "Measuring…" : "Run the remote benchmark"}
          </Button>
        </p>
        <FieldError message={formError(benchmark.error, [])} />
      </section>

      <section className={cardClass} aria-label="Hourly rate">
        <h2>Hourly rate</h2>
        <Label htmlFor="hourly-rate">Euros per hour (for the cost estimate below)</Label>
        <Input id="hourly-rate" value={shownRate} onChange={(event) => setRate(event.target.value)} />
        <FieldError message={fieldError(saveRate.error, "hourly_rate_eur")} />
        <p>
          <Button
            type="button"
            variant="outline"
            onClick={() => saveRate.mutate(Number(shownRate.replace(",", ".")))}
          >
            Save the rate
          </Button>
        </p>
      </section>

      <h2>Recent remote jobs</h2>
      {data.jobs.length === 0 ? (
        <p>No render has run on the server yet.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Render</TableHead>
              <TableHead>Estimate</TableHead>
              <TableHead>Actual</TableHead>
              <TableHead>Transfer</TableHead>
              <TableHead>Outcome</TableHead>
              <TableHead>Cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.jobs.map((job) => (
              <TableRow key={job.started_at + job.render}>
                <TableCell>
                  {job.package_id} v{job.version} {job.render}
                </TableCell>
                <TableCell>{seconds(job.estimate_seconds)}</TableCell>
                <TableCell>{seconds(job.actual_seconds)}</TableCell>
                <TableCell>{seconds(job.transfer_seconds)}</TableCell>
                <TableCell>{job.error ? `${job.outcome}: ${job.error}` : job.outcome}</TableCell>
                <TableCell>{euros(job)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Page>
  );
}
