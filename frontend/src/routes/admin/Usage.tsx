import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { Page } from "@/components/Page";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";

export default function Usage() {
  const usage = useQuery({ queryKey: ["admin-usage"], queryFn: () => api.usage(1) });
  if (!usage.data) return <Page>Loading…</Page>;
  return (
    <Page>
      <h1>Usage</h1>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Model</TableHead>
            <TableHead>Day</TableHead>
            <TableHead>Input</TableHead>
            <TableHead>Output</TableHead>
            <TableHead>Calls</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {usage.data.map((row) => (
            <TableRow key={`${row.model}-${row.day}`}>
              <TableCell>{row.model}</TableCell>
              <TableCell>{row.day}</TableCell>
              <TableCell>{row.input_tokens}</TableCell>
              <TableCell>{row.output_tokens}</TableCell>
              <TableCell>{row.calls}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Page>
  );
}
