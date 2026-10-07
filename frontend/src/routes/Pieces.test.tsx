import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  render(<QueryClientProvider client={client}><Pieces /></QueryClientProvider>);
}

function serve(renders: unknown[], overrides: (call: string) => { status?: number; body?: unknown } | undefined = () => undefined) {
  return stubFetch((call) => {
    const mine = overrides(call);
    if (mine) return mine;
    if (call === "GET /packages") return { body: [{ package_id: "bench", versions: [2, 1] }] };
    if (call === "GET /packages/bench/versions/2/renders") return { body: renders };
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
