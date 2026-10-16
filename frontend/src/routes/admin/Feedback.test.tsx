import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
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

test("version verdicts are counted per agent and model, with a no-agent row, and a row lists its notes", async () => {
  const user = userEvent.setup();
  const designer = "~deepseek/deepseek-v4-flash-latest";
  const calls = stubFetch((call) => {
    if (call === "GET /admin/feedback?days=30") return { body: [] };
    if (call === "GET /admin/feedback/verdicts?days=30") {
      return { body: [
        { slot: "designer", model: designer, matches: 1, mismatch: 2, latest_note_at: "2026-10-16T10:00:00Z" },
        { slot: null, model: null, matches: 0, mismatch: 1, latest_note_at: "2026-10-16T09:00:00Z" },
      ] };
    }
    if (call.startsWith("GET /admin/feedback/verdicts/notes")) {
      return { body: [
        { package_id: "amesbury-wardrobe", version: 6, verdict: "mismatch", status: "open", note: "second", updated_at: "b" },
        { package_id: "amesbury-wardrobe", version: 5, verdict: "mismatch", status: "resolved", note: "first", updated_at: "a" },
      ] };
    }
  });
  show();
  const section = await screen.findByRole("region", { name: "Version verdicts" });
  expect(within(section).getByText(designer)).toBeInTheDocument();
  await user.click(within(section).getByRole("button", { name: "Show verdict notes for no agent · no model" }));
  expect(calls.some(([, url]) => url === "/admin/feedback/verdicts/notes?slot=&model=")).toBe(true);
  const notes = await screen.findByRole("region", { name: "Verdict notes" });
  expect([...notes.querySelectorAll("li")].map((li) => li.textContent)).toEqual([
    "amesbury-wardrobe v6 (doesn't match, open): second",
    "amesbury-wardrobe v5 (doesn't match, resolved): first",
  ]);
});
