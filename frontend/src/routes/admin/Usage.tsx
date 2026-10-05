import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";

export default function Usage() {
  const usage = useQuery({ queryKey: ["admin-usage"], queryFn: () => api.usage(1) });
  if (!usage.data) return <main>Loading…</main>;
  return (
    <main>
      <h1>Usage</h1>
      <table>
        <thead>
          <tr>
            <th>Model</th>
            <th>Day</th>
            <th>Input</th>
            <th>Output</th>
            <th>Calls</th>
          </tr>
        </thead>
        <tbody>
          {usage.data.map((row) => (
            <tr key={`${row.model}-${row.day}`}>
              <td>{row.model}</td>
              <td>{row.day}</td>
              <td>{row.input_tokens}</td>
              <td>{row.output_tokens}</td>
              <td>{row.calls}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
