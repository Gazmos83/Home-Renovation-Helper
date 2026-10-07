import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import Pieces from "./Pieces";

const turntable = {
  render: "turntable", label: "Turntable", tier: "draft", can_rate: true, rating: null, comment: null,
  preview: "/packages/bench/versions/2/files/frames/0", viewer: "/packages/bench/versions/2/files/viewer.html",
};
const legacy = { ...turntable, render: "still", label: "Still", can_rate: false, viewer: null,
  preview: "/packages/bench/versions/2/files/still.png" };

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><Pieces /></MemoryRouter></QueryClientProvider>);
}

function info(version: number, approvedVersion: number | null, status = "succeeded") {
  return {
    package_id: "bench", version, status,
    approved_at: version === approvedVersion ? "2026-10-07T10:00:00+00:00" : null,
  };
}

function serve(
  renders: unknown[],
  overrides: (call: string) => { status?: number; body?: unknown } | undefined = () => undefined,
  state: { approved: number | null; status?: string } = { approved: null },
) {
  return stubFetch((call) => {
    const mine = overrides(call);
    if (mine) return mine;
    if (call === "GET /packages") return { body: [{ package_id: "bench", versions: [2, 1] }] };
    if (call === "GET /packages/bench/versions/2/renders") return { body: renders };
    const read = /^GET \/packages\/bench\/versions\/(\d)$/.exec(call);
    if (read) return { body: info(Number(read[1]), state.approved, state.status) };
    const change = /^(PUT|DELETE) \/packages\/bench\/versions\/(\d)\/approval$/.exec(call);
    if (change) {
      state.approved = change[1] === "PUT" ? Number(change[2]) : null;
      return { body: info(Number(change[2]), state.approved) };
    }
  });
}

test("a render shows its preview, tier and viewer link", async () => {
  serve([turntable]);
  show();
  expect(await screen.findByRole("img", { name: "Turntable of bench version 2" })).toHaveAttribute("src", turntable.preview);
  expect(screen.getByText("draft")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open the turntable viewer" })).toHaveAttribute("href", turntable.viewer);
});

test("rating down with a comment is sent, shown and survives a reload of the list", async () => {
  const user = userEvent.setup();
  let stored: unknown = null;
  const calls = serve([turntable], (call) => {
    if (call === "PUT /packages/bench/versions/2/renders/turntable/feedback") {
      stored = { ...turntable, rating: "down", comment: "too dark" };
      return { body: stored };
    }
    if (call === "GET /packages/bench/versions/2/renders" && stored) return { body: [stored] };
  });
  show();
  await user.type(await screen.findByLabelText("Comment on Turntable"), "too dark");
  await user.click(screen.getByRole("button", { name: "Thumbs down Turntable" }));
  expect(await screen.findByRole("button", { name: "Thumbs down Turntable", pressed: true })).toBeInTheDocument();
  expect(calls.find(([m]) => m === "PUT")![2]).toEqual({ rating: "down", comment: "too dark" });
  expect(screen.getByLabelText("Comment on Turntable")).toHaveValue("too dark");
});

test("clearing a rating calls the API and unpresses the thumbs", async () => {
  const user = userEvent.setup();
  let cleared = false;
  const rated = { ...turntable, rating: "up", comment: "nice" };
  const calls = serve([rated], (call) => {
    if (call === "DELETE /packages/bench/versions/2/renders/turntable/feedback") {
      cleared = true;
      return { body: turntable };
    }
    if (call === "GET /packages/bench/versions/2/renders" && cleared) return { body: [turntable] };
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Clear rating of Turntable" }));
  expect(await screen.findByRole("button", { name: "Thumbs up Turntable", pressed: false })).toBeInTheDocument();
  expect(calls.some(([m]) => m === "DELETE")).toBe(true);
});

test("a refusal is shown beside the render it names and the optimistic rating is rolled back", async () => {
  const user = userEvent.setup();
  serve([turntable], (call) => {
    if (call.startsWith("PUT")) {
      return { status: 409, body: { detail: { failure_class: "no_render", reason: "the render does not exist yet, so it cannot be rated" } } };
    }
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Thumbs up Turntable" }));
  const message = await screen.findByText("the render does not exist yet, so it cannot be rated");
  expect(message.closest("section")).toHaveAccessibleName("Turntable");
  expect(screen.getByRole("button", { name: "Thumbs up Turntable", pressed: false })).toBeInTheDocument();
});

test("a render made before ratings existed says so and offers no thumbs", async () => {
  serve([legacy]);
  show();
  expect(await screen.findByText("Rendered before ratings existed — render it again to rate it.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Thumbs/ })).toBeNull();
});

test("no model, prompt, token or cost text appears on the page", async () => {
  serve([turntable]);
  show();
  await screen.findByRole("img");
  const text = document.body.textContent ?? "";
  for (const word of [/deepseek/i, /prompt/i, /token/i, /\bmodel\b/i, /€|eur\b/i, /\bcost/i]) {
    expect(text).not.toMatch(word);
  }
});

test("a packages refusal is shown instead of loading forever", async () => {
  stubFetch((call) =>
    call === "GET /packages" ? { status: 500, body: { detail: "the packages list failed" } } : undefined,
  );
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent("the packages list failed");
  expect(screen.queryByText("Loading…")).not.toBeInTheDocument();
});

test("another version loads its own renders", async () => {
  const user = userEvent.setup();
  serve([turntable], (call) => {
    if (call === "GET /packages/bench/versions/1/renders") return { body: [] };
  });
  show();
  await screen.findByRole("img");
  await user.click(screen.getByRole("button", { name: "Version 1" }));
  expect(await screen.findByText("No renders of this version yet.")).toBeInTheDocument();
});

test("a built version is approved from the page and the badge shows without a reload", async () => {
  const user = userEvent.setup();
  const state = { approved: null as number | null };
  const calls = serve([turntable], undefined, state);
  show();
  expect(await screen.findByText("No version approved yet.")).toBeInTheDocument();
  await user.click(await screen.findByRole("button", { name: "Approve version 2" }));
  expect(await screen.findByText("Approved: version 2")).toBeInTheDocument();
  expect(screen.getByText("Approved")).toBeInTheDocument();
  expect(calls.some(([m, u]) => m === "PUT" && u === "/packages/bench/versions/2/approval")).toBe(true);
  expect(screen.getByRole("button", { name: "Unapprove version 2" })).toBeInTheDocument();
});

test("an approved version is unapproved and the page shows no approved version", async () => {
  const user = userEvent.setup();
  const state = { approved: 2 as number | null };
  const calls = serve([turntable], undefined, state);
  show();
  expect(await screen.findByText("Approved: version 2")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Unapprove version 2" }));
  expect(await screen.findByText("No version approved yet.")).toBeInTheDocument();
  expect(screen.queryByText("Approved")).toBeNull();
  expect(calls.some(([m]) => m === "DELETE")).toBe(true);
});

test("a version that is not built offers no approval", async () => {
  serve([turntable], undefined, { approved: null, status: "running" });
  show();
  await screen.findByRole("img");
  expect(screen.queryByRole("button", { name: /Approve version/ })).toBeNull();
});

test("an approval refusal is shown next to the version it names", async () => {
  const user = userEvent.setup();
  serve([turntable], (call) => {
    if (call === "PUT /packages/bench/versions/2/approval") {
      return { status: 409, body: { detail: { failure_class: "not_built", reason: "version 2 must be built before it can be approved" } } };
    }
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Approve version 2" }));
  const refusal = await screen.findByText("version 2 must be built before it can be approved");
  expect(refusal.closest("[role=group]")).toHaveAccessibleName("Approval of bench version 2");
  expect(screen.getByRole("button", { name: "Approve version 2" })).toBeEnabled();
});

test("the import template is offered with how to use it", async () => {
  serve([turntable]);
  show();
  const link = await screen.findByRole("link", { name: "Download the import template" });
  expect(link).toHaveAttribute("href", "/design-import/template");
  expect(link).toHaveAttribute("download", "import-template.json");
  expect(screen.getByText(/give it to another AI chat to fill in/)).toBeInTheDocument();
});

test("a built version offers the design and the bundle downloads", async () => {
  serve([turntable]);
  show();
  const design = await screen.findByRole("link", { name: "Download design (version 2)" });
  expect(design).toHaveAttribute("href", "/packages/bench/versions/2/design");
  expect(design).toHaveAttribute("download", "bench-v2.json");
  const bundle = await screen.findByRole("link", { name: "Download bundle (version 2)" });
  expect(bundle).toHaveAttribute("href", "/packages/bench/versions/2/bundle");
  expect(bundle).toHaveAttribute("download", "bench-v2.zip");
  expect(screen.getByRole("link", { name: "Inspect version 2" })).toHaveAttribute("href", "/pieces/bench/versions/2");
});

test("a version still building offers the design but not the bundle", async () => {
  serve([turntable], undefined, { approved: null, status: "running" });
  show();
  expect(await screen.findByRole("link", { name: "Download design (version 2)" })).toBeInTheDocument();
  await screen.findByRole("img");
  expect(screen.queryByRole("link", { name: /Download bundle/ })).toBeNull();
  expect(screen.queryByRole("link", { name: /Inspect/ })).toBeNull();
});
