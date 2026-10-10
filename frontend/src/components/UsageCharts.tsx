import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import { api, type UsageGroup } from "../lib/api";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ROLE_LABELS } from "@/components/chat/roles";

type Metric = "calls" | "tokens" | "cost";
const RANGES = [7, 30, 90] as const;
const METRICS: { value: Metric; label: string }[] = [
  { value: "calls", label: "Calls" },
  { value: "tokens", label: "Tokens (input + output)" },
  { value: "cost", label: "Estimated cost (USD)" },
];

function value(group: UsageGroup, metric: Metric): number {
  if (metric === "calls") return group.calls;
  if (metric === "tokens") return group.input_tokens + group.output_tokens;
  return group.cost_usd;
}

function Chart({ title, groups, metric, label }: { title: string; groups: UsageGroup[]; metric: Metric; label?: (key: string) => string }) {
  const data = groups.map((group) => ({ name: label ? label(group.key) : group.key, value: value(group, metric) }));
  return (
    <figure className="space-y-1">
      <figcaption className="font-medium">{title}</figcaption>
      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">No calls in this range.</p>
      ) : (
        <BarChart width={640} height={220} data={data} aria-label={title}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey="value" fill="currentColor" className="text-primary" />
        </BarChart>
      )}
      <ul className="sr-only">
        {data.map((row) => (
          <li key={row.name}>
            {row.name}: {row.value}
          </li>
        ))}
      </ul>
    </figure>
  );
}

/** Calls, tokens and estimated cost per model, per day and per agent (dev-panel-insights). */
export function UsageCharts() {
  const [days, setDays] = useState<7 | 30 | 90>(7);
  const [metric, setMetric] = useState<Metric>("calls");
  const summary = useQuery({ queryKey: ["admin-usage-summary", days], queryFn: () => api.usageSummary(days) });

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <Label className="flex items-center gap-2">
          Range
          <Select value={String(days)} onChange={(event) => setDays(Number(event.target.value) as 7 | 30 | 90)}>
            {RANGES.map((range) => (
              <option key={range} value={range}>
                Last {range} days
              </option>
            ))}
          </Select>
        </Label>
        <Label className="flex items-center gap-2">
          Show
          <Select value={metric} onChange={(event) => setMetric(event.target.value as Metric)}>
            {METRICS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Label>
      </div>
      {summary.data && (
        <>
          <p className="text-sm text-muted-foreground">
            Tracing is {summary.data.tracing ? "on: each call links to its Langfuse trace" : "off"}.
            {metric === "cost" && ` Costs are an ${summary.data.label}.`}
            {metric === "cost" && summary.data.cost_incomplete && " Cost is incomplete: some models have no price."}
          </p>
          <Chart title="Per agent" groups={summary.data.slot} metric={metric} label={(key) => ROLE_LABELS[key] ?? key} />
          <Chart title="Per model" groups={summary.data.model} metric={metric} />
          <Chart title="Per day" groups={summary.data.day} metric={metric} />
        </>
      )}
    </section>
  );
}
