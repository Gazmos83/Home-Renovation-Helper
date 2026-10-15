import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type OffloadJob, type OffloadPod, type OffloadPodSession } from "../../lib/api";
import { FieldError, fieldError, formError } from "../../lib/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cardClass } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const seconds = (value: number | null) => (value === null ? "—" : `${value.toFixed(1)} s`);
const euros = (job: OffloadJob) => (job.cost_eur === null ? "—" : `€${job.cost_eur.toFixed(2)}`);
const dollars = (row: OffloadPodSession) => (row.cost_usd === null ? "—" : `$${row.cost_usd.toFixed(2)}`);
const clock = (iso: string) => iso.slice(11, 16);
const stamp = (iso: string) => iso.slice(0, 16).replace("T", " ");
const lifetime = (total: number) => `${Math.floor(total / 60)} min ${total % 60} s`;

function podState(pod: OffloadPod): string {
  switch (pod.state) {
    case "starting":
      return "Starting a pod…";
    case "running":
      return pod.delete_at
        ? `Running (${pod.pod_id}) · deleted at ${clock(pod.delete_at)} UTC if still idle`
        : `Running (${pod.pod_id}) · a render is using it`;
    case "delete_failed":
      return `Delete failed (${pod.pod_id}): ${pod.error ?? "unknown error"}. Retried every minute; check the RunPod console.`;
    default:
      return `No pod running. One is created after a final is approved and deleted after ${pod.idle_minutes} idle minutes.`;
  }
}

export default function Offload() {
  const queryClient = useQueryClient();
  const summary = useQuery({ queryKey: ["admin-offload"], queryFn: api.offload });
  const [rate, setRate] = useState<string | null>(null);
  const [idle, setIdle] = useState<string | null>(null);
  const reload = () => queryClient.invalidateQueries({ queryKey: ["admin-offload"] });

  const test = useMutation({ mutationFn: api.testOffload });
  const benchmark = useMutation({ mutationFn: api.offloadBenchmark, onSuccess: reload });
  const target = useMutation({ mutationFn: api.setOffloadTarget, onSuccess: reload });
  const deletePod = useMutation({ mutationFn: api.deleteOffloadPod, onSuccess: reload });
  const saveIdle = useMutation({
    mutationFn: (value: number) => api.setOffloadIdle(value),
    onSuccess: () => {
      setIdle(null);
      reload();
    },
  });
  const saveRate = useMutation({
    mutationFn: (value: number) => api.setOffloadRate(value),
    onSuccess: () => {
      setRate(null);
      reload();
    },
  });

  if (!summary.data) return <>Loading…</>;
  const data = summary.data;
  const shownRate = rate ?? (data.hourly_rate_eur === null ? "" : String(data.hourly_rate_eur));
  const pod = data.mode === "pod" ? data.pod : null;
  const shownIdle = idle ?? (pod ? String(pod.idle_minutes) : "");

  return (
    <>

      <section className={cardClass} aria-label="Render server">
        <h2>Render server</h2>
        {pod ? (
          <p>
            RunPod pod · {pod.gpu_types.join(" > ")} · image {pod.image} · volume {pod.volume_id} · Blender at {data.blender} ·{" "}
            {data.device}
          </p>
        ) : data.configured ? (
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
        {test.data && "runpod_ok" in test.data && (
          <p role="status">
            {test.data.runpod_ok ? "RunPod accepts the key" : "RunPod not usable"}
            {test.data.volume_found && ` · volume found in ${test.data.data_center}`}
            {test.data.reason && ` · ${test.data.reason}`}
            {" · no pod was started"}
          </p>
        )}
        {test.data && "reachable" in test.data && (
          <p role="status">
            {test.data.reachable ? "Reachable" : "Not reachable"}
            {test.data.blender_version &&
              ` · Blender ${test.data.blender_version}${test.data.version_ok ? "" : ` (needs ${test.data.pinned_version})`}`}
            {test.data.gpus.length > 0 && ` · GPUs: ${test.data.gpus.join(", ")}`}
            {test.data.version_ok && test.data.gpus.length === 0 && " · no GPU listed"}
          </p>
        )}
      </section>

      {pod && (
        <section className={cardClass} aria-label="Render pod">
          <h2>Render pod</h2>
          <p role="status">{podState(pod)}</p>
          <p>
            <Button
              type="button"
              variant="outline"
              disabled={pod.state === "none" || deletePod.isPending}
              onClick={() => deletePod.mutate()}
            >
              Delete pod now
            </Button>
          </p>
          <FieldError message={formError(deletePod.error, [])} />
          <Label htmlFor="idle-minutes">Minutes an idle pod is kept (1–120)</Label>
          <Input id="idle-minutes" inputMode="numeric" value={shownIdle} onChange={(event) => setIdle(event.target.value)} />
          <FieldError message={fieldError(saveIdle.error, "idle_minutes")} />
          <p>
            <Button type="button" variant="outline" onClick={() => saveIdle.mutate(Number(shownIdle))}>
              Save the idle time
            </Button>
          </p>
        </section>
      )}

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

      {pod && (
        <>
          <h2>Pod sessions</h2>
          {data.pod_sessions.length === 0 ? (
            <p>No pod has been created yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Created</TableHead>
                  <TableHead>GPU</TableHead>
                  <TableHead>Lifetime</TableHead>
                  <TableHead>Jobs</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead>Cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.pod_sessions.map((row) => (
                  <TableRow key={row.created_at + row.pod_id}>
                    <TableCell>{stamp(row.created_at)}</TableCell>
                    <TableCell>{row.gpu_type}</TableCell>
                    <TableCell>{lifetime(row.lifetime_seconds)}</TableCell>
                    <TableCell>{row.jobs}</TableCell>
                    <TableCell>{row.error ? `${row.outcome}: ${row.error}` : row.outcome}</TableCell>
                    <TableCell>{dollars(row)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </>
      )}
    </>
  );
}
