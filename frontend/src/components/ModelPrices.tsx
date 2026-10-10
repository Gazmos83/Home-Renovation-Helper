import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

function perMillion(value: number | null): string {
  return value === null ? "no price" : `$${value.toFixed(value < 1 ? 4 : 2)}`;
}

/** Each registry slug's price per million tokens, refreshed from OpenRouter on request (dev-panel-insights). */
export function ModelPrices() {
  const queryClient = useQueryClient();
  const prices = useQuery({ queryKey: ["admin-model-prices"], queryFn: api.modelPrices });
  const refresh = useMutation({
    mutationFn: api.refreshModelPrices,
    onSuccess: (rows) => queryClient.setQueryData(["admin-model-prices"], rows),
  });

  return (
    <section className="space-y-2">
      <h1>Prices</h1>
      <p className="text-sm text-muted-foreground">
        From OpenRouter's model list, per million tokens. Costs on the Calls page are estimates at these prices.
      </p>
      <Button type="button" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
        {refresh.isPending ? "Refreshing…" : "Refresh prices"}
      </Button>
      {refresh.error instanceof Error && (
        <p className="text-sm text-destructive">Prices were not refreshed: {refresh.error.message}</p>
      )}
      {prices.data && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Model</TableHead>
              <TableHead>Input</TableHead>
              <TableHead>Output</TableHead>
              <TableHead>Fetched</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {prices.data.map((row) => (
              <TableRow key={row.slug}>
                <TableCell>{row.slug}</TableCell>
                <TableCell>{perMillion(row.input_per_million_usd)}</TableCell>
                <TableCell>{perMillion(row.output_per_million_usd)}</TableCell>
                <TableCell>{row.fetched_at ? new Date(row.fetched_at).toLocaleDateString() : "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
