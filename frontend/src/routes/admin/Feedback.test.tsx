import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import Feedback from "./Feedback";

const MODEL = "deepseek/deepseek-v4-pro-0813";

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Feedback /></QueryClientProvider>);
}

test("ratings are grouped per agent, model and tier and a row lists its comments", async () => {
  const user = userEvent.setup();
  const calls = stubFetch((call) => {
    if (call === "GET /admin/feedback?days=30") {
      return { body: [
        { slot: "builder", model: MODEL, tier: "draft", up: 2, down: 1, latest_comment_at: "2026-10-06T10:00:00Z" },
        { slot: null, model: null, tier: "draft", up: 1, down: 0, latest_comment_at: null },
      ] };
    }
    if (call.startsWith("GET /admin/feedback/comments")) {
      return { body: [{ package_id: "bench", version: 1, render_key: "turntable", rating: "down", comment: "too dark", at: "2026-10-06T10:00:00Z" }] };
    }
  });
  show();
  expect(await screen.findByText(MODEL)).toBeInTheDocument();
  expect(screen.getByText("2")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: `Show comments for builder · ${MODEL} · draft` }));
  expect(await screen.findByText(/too dark/)).toBeInTheDocument();
  expect(calls.some(([, url]) => url === `/admin/feedback/comments?tier=draft&slot=builder&model=${encodeURIComponent(MODEL)}`)).toBe(true);
  await user.click(screen.getByRole("button", { name: "Show comments for no agent · no model · draft" }));
  expect(calls.some(([, url]) => url === "/admin/feedback/comments?tier=draft&slot=&model=")).toBe(true);
});

test("an empty summary says there are no ratings", async () => {
  stubFetch((call) => (call === "GET /admin/feedback?days=30" ? { body: [] } : undefined));
  show();
  expect(await screen.findByText("No ratings yet.")).toBeInTheDocument();
});
