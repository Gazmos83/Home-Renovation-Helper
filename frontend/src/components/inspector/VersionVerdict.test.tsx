import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import { VersionVerdict } from "./VersionVerdict";

/** version-verdict: the inspector's verdict section, with or without a render. */

const BASE = "/packages/amesbury-wardrobe/versions";
const DRAWERS = "the side sections lost their 5 drawers";
type Stored = { verdict: string; note: string | null; status: string | null; updated_at: string } | null;

function serve(initial: Record<number, Stored> = {}) {
  const store: Record<number, Stored> = { ...initial };
  const calls = stubFetch((call, init) => {
    const match = /^(\w+) \/packages\/amesbury-wardrobe\/versions\/(\d+)\/verdict(\/status)?$/.exec(call);
    if (!match) return undefined;
    const [, method, n, status] = match;
    const version = Number(n);
    const body = typeof init.body === "string" ? JSON.parse(init.body) : {};
    if (method === "PUT") {
      store[version] = {
        verdict: body.verdict,
        note: body.note ?? null,
        status: body.verdict === "mismatch" ? "open" : null,
        updated_at: "2026-10-16T10:00:00Z",
      };
    } else if (method === "DELETE") store[version] = null;
    else if (method === "PATCH" && status) store[version] = { ...store[version]!, status: body.status };
    return { body: { verdict: store[version] ?? null } };
  });
  return calls;
}

function show(version = 4) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={client}>
      <VersionVerdict key={version} packageId="amesbury-wardrobe" version={version} />
    </QueryClientProvider>,
  );
  return { client, view };
}

const up = () => screen.getByRole("button", { name: "Matches what I confirmed" });
const down = () => screen.getByRole("button", { name: "Doesn't match what I confirmed" });

test("with no verdict only the two thumbs are shown, no note field", async () => {
  serve();
  show();
  await screen.findByRole("button", { name: "Matches what I confirmed" });
  expect(down()).toHaveAttribute("aria-pressed", "false");
  expect(screen.queryByLabelText("Verdict note")).not.toBeInTheDocument();
});

test("thumbs down opens the note field and an empty note saves nothing", async () => {
  const calls = serve();
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Doesn't match what I confirmed" }));
  expect(screen.getByLabelText("Verdict note")).toHaveAttribute("placeholder", "What doesn't match?");
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Write what doesn't match before saving.");
  expect(calls.filter(([method]) => method === "PUT")).toHaveLength(0);
});

test("a saved thumbs down shows its note and open, and resolving hides resolve and dismiss", async () => {
  const calls = serve();
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Doesn't match what I confirmed" }));
  await user.type(screen.getByLabelText("Verdict note"), `${DRAWERS}{Enter}`);
  const section = screen.getByRole("region", { name: "Verdict" });
  await within(section).findByText("open");
  expect(down()).toHaveAttribute("aria-pressed", "true");
  // Saved: the note is text with "Saved" (Blockout marked wrong in the inspector).
  expect(within(section).getByText(DRAWERS)).toBeInTheDocument();
  expect(within(section).getByText("Saved")).toBeInTheDocument();
  expect(screen.queryByLabelText("Verdict note")).not.toBeInTheDocument();
  expect(calls).toContainEqual(["PUT", `${BASE}/4/verdict`, { verdict: "mismatch", note: DRAWERS }]);
  await user.click(screen.getByRole("button", { name: "Mark resolved" }));
  expect(await within(section).findByText("resolved")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Mark resolved" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Dismiss" })).not.toBeInTheDocument();
});

test("thumbs up saves at once, shows an optional note field, and pressing it again clears", async () => {
  const calls = serve();
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Matches what I confirmed" }));
  await waitFor(() => expect(up()).toHaveAttribute("aria-pressed", "true"));
  expect(calls).toContainEqual(["PUT", `${BASE}/4/verdict`, { verdict: "matches" }]);
  expect(screen.getByLabelText("Verdict note")).toHaveAttribute("placeholder", "Add a note (optional)");
  await user.type(screen.getByLabelText("Verdict note"), "spot on{Enter}");
  expect(calls).toContainEqual(["PUT", `${BASE}/4/verdict`, { verdict: "matches", note: "spot on" }]);
  await user.click(up());
  await waitFor(() => expect(up()).toHaveAttribute("aria-pressed", "false"));
  expect(calls.map(([m]) => m)).toContain("DELETE");
  expect(screen.queryByLabelText("Verdict note")).not.toBeInTheDocument();
});

test("each version shows its own verdict", async () => {
  serve({ 3: { verdict: "matches", note: null, status: null, updated_at: "x" }, 4: null });
  const { client, view } = show(3);
  await waitFor(() => expect(up()).toHaveAttribute("aria-pressed", "true"));
  view.rerender(
    <QueryClientProvider client={client}>
      <VersionVerdict key={4} packageId="amesbury-wardrobe" version={4} />
    </QueryClientProvider>,
  );
  await waitFor(() => expect(up()).toHaveAttribute("aria-pressed", "false"));
  expect(screen.queryByLabelText("Verdict note")).not.toBeInTheDocument();
});

test("no model, token or cost text appears", async () => {
  serve({ 4: { verdict: "mismatch", note: DRAWERS, status: "open", updated_at: "x" } });
  show();
  const section = await screen.findByRole("region", { name: "Verdict" });
  await within(section).findByText(DRAWERS);
  for (const word of ["model", "token", "cost", "deepseek", "designer"]) {
    expect(section.textContent?.toLowerCase()).not.toContain(word);
  }
});

// --- the note saves visibly (render-now-blueprints-verdict-note) ---

test("a thumbs-up note saved with Enter is sent once and shown as saved (Note on a thumbs up saved with Enter)", async () => {
  const calls = serve({ 4: { verdict: "matches", note: null, status: null, updated_at: "x" } });
  show();
  const user = userEvent.setup();
  const field = await screen.findByLabelText("Verdict note");
  await user.type(field, "drawer heights are right");
  expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  await user.keyboard("{Enter}{Enter}");
  const section = screen.getByRole("region", { name: "Verdict" });
  expect(await within(section).findByText("Saved")).toBeInTheDocument();
  expect(within(section).getByText("drawer heights are right")).toBeInTheDocument();
  expect(within(section).getByRole("button", { name: "Edit" })).toBeInTheDocument();
  expect(calls.filter(([method]) => method === "PUT")).toHaveLength(1);
});

test("leaving the field saves nothing", async () => {
  const calls = serve({ 4: { verdict: "matches", note: null, status: null, updated_at: "x" } });
  show();
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Verdict note"), "half a thought");
  await user.tab();
  expect(calls.filter(([method]) => method === "PUT")).toHaveLength(0);
});

test("a saved note is edited and saved again (Note edited)", async () => {
  const calls = serve({ 4: { verdict: "matches", note: "spot on", status: null, updated_at: "x" } });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Edit" }));
  const field = screen.getByLabelText("Verdict note");
  expect(field).toHaveValue("spot on");
  await user.clear(field);
  await user.type(field, "spot on, check the plinth");
  await user.click(screen.getByRole("button", { name: "Save" }));
  const section = screen.getByRole("region", { name: "Verdict" });
  expect(await within(section).findByText("spot on, check the plinth")).toBeInTheDocument();
  expect(within(section).getByText("Saved")).toBeInTheDocument();
  expect(calls).toContainEqual(["PUT", `${BASE}/4/verdict`, { verdict: "matches", note: "spot on, check the plinth" }]);
});

test("Escape cancels an edit and shows the saved note again (Edit cancelled)", async () => {
  const calls = serve({ 4: { verdict: "matches", note: "spot on", status: null, updated_at: "x" } });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Edit" }));
  await user.type(screen.getByLabelText("Verdict note"), " and more");
  await user.keyboard("{Escape}");
  const section = screen.getByRole("region", { name: "Verdict" });
  expect(within(section).getByText("spot on")).toBeInTheDocument();
  expect(screen.queryByLabelText("Verdict note")).not.toBeInTheDocument();
  expect(calls.filter(([method]) => method === "PUT")).toHaveLength(0);
});
