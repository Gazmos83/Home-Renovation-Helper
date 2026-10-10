import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import ConversationCalls from "./ConversationCalls";

const threads = [
  { thread_id: "t1", title: "Hall bench", package_id: null, created_at: "", last_turn_at: "2026-10-07T09:00:00Z" },
  { thread_id: "t2", title: "", package_id: null, created_at: "", last_turn_at: "2026-10-06T09:00:00Z" },
];

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ConversationCalls />
    </QueryClientProvider>,
  );
}

test("a conversation's calls are listed with their specialist, model slug and tokens", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /chat/threads") return { body: threads };
    if (call === "GET /admin/threads/t1/calls")
      return {
        body: [
          { time: "2026-10-07T09:00:02Z", slot: "designer", operation: "chat.designer", model: "deepseek/deepseek-v4-pro-0813", input_tokens: 900, output_tokens: 120, estimated: false },
          { time: "2026-10-07T09:00:01Z", slot: "foreman", operation: "chat.foreman", model: "openai/gpt-5.6-luna", input_tokens: 400, output_tokens: null, estimated: true },
        ],
      };
    if (call === "GET /admin/threads/t2/calls") return { body: [] };
  });
  show();
  const table = await screen.findByRole("table");
  const rows = within(table).getAllByRole("row").slice(1);
  expect(within(rows[0]).getByText("Designer")).toBeInTheDocument();
  expect(within(rows[0]).getByText("deepseek/deepseek-v4-pro-0813")).toBeInTheDocument();
  expect(within(rows[0]).getByText("900")).toBeInTheDocument();
  expect(within(rows[1]).getByText("Foreman")).toBeInTheDocument();
  expect(within(rows[1]).getByText("openai/gpt-5.6-luna")).toBeInTheDocument();
  expect(within(rows[1]).getByText("(estimate)")).toBeInTheDocument();

  await userEvent.setup().selectOptions(screen.getByLabelText("Conversation"), "t2");
  expect(await screen.findByText("No model calls recorded for this conversation.")).toBeInTheDocument();
  expect(calls.map(([, url]) => url)).toContain("/admin/threads/t2/calls");
});

const summary = {
  days: 7, cost_incomplete: true, label: "estimate at the last fetched price", tracing: true,
  model: [{ key: "deepseek/deepseek-v4-pro-0813", calls: 3, input_tokens: 900, output_tokens: 120, estimated_calls: 0, cost_usd: 0.01, cost_complete: true }],
  day: [{ key: "2026-10-07", calls: 4, input_tokens: 1300, output_tokens: 120, estimated_calls: 1, cost_usd: 0.01, cost_complete: false }],
  slot: [
    { key: "designer", calls: 3, input_tokens: 900, output_tokens: 120, estimated_calls: 0, cost_usd: 0.01, cost_complete: true },
    { key: "reviewer", calls: 1, input_tokens: 400, output_tokens: 0, estimated_calls: 1, cost_usd: 0, cost_complete: false },
  ],
};

test("totals per agent, model and day are drawn, and a call links to its Langfuse trace", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /chat/threads") return { body: threads };
    if (call.startsWith("GET /admin/usage/summary")) return { body: summary };
    if (call === "GET /admin/threads/t1/calls")
      return {
        body: [
          { time: "2026-10-07T09:00:02Z", slot: "designer", operation: "chat.designer", model: "m", input_tokens: 9, output_tokens: 1, estimated: false, trace_url: "https://cloud.langfuse.com/project/p/traces/abc" },
        ],
      };
  });
  show();
  expect(await screen.findByText("Per agent")).toBeInTheDocument();
  expect(screen.getByText("Designer: 3")).toBeInTheDocument();
  expect(screen.getByText("Reviewer: 1")).toBeInTheDocument();
  expect(screen.getByText(/Tracing is on/)).toBeInTheDocument();
  const link = await screen.findByRole("link", { name: "Langfuse" });
  expect(link).toHaveAttribute("href", "https://cloud.langfuse.com/project/p/traces/abc");
  expect(link).toHaveAttribute("target", "_blank");

  await userEvent.setup().selectOptions(screen.getByLabelText("Range"), "30");
  expect(calls.map(([, url]) => url)).toContain("/admin/usage/summary?days=30");
  await userEvent.setup().selectOptions(screen.getByLabelText("Show"), "cost");
  expect(await screen.findByText(/Cost is incomplete/)).toBeInTheDocument();
});
