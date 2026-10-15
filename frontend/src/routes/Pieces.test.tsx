import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import Pieces from "./Pieces";

const turntable = {
  render: "turntable", label: "Turntable", tier: "draft", finished_at: null, frames: 12, can_rate: true, rating: null, comment: null,
  preview: "/packages/bench/versions/2/files/frames/0", viewer: "/packages/bench/versions/2/files/viewer.html",
};
const still = {
  render: "still", label: "Still", tier: "draft", finished_at: null, frames: 0, can_rate: true, rating: null, comment: null,
  preview: "/packages/bench/versions/2/files/still.png", viewer: null,
};
const legacy = { ...still, can_rate: false };
const variant = {
  render: "variant:walnut-draft", label: "Walnut", tier: "draft", finished_at: null, frames: 12, can_rate: true,
  rating: null, comment: null, preview: "/packages/bench/versions/2/files/variants/walnut-draft/frames/0", viewer: null,
};

function summary(name: string) {
  return {
    name, width_mm: 3000, depth_mm: 2000, corners: 4, height_mm: 2500, openings: 1,
    apartment: null, pieces: [], conversations: 0, composition: null,
  };
}

function Address() {
  const location = useLocation();
  return <output aria-label="address">{location.pathname + location.search}</output>;
}

/** The Pieces tab at `path`; by default with the `bench` dialog open, which holds what its card held. */
function show(path = "/studio/pieces/bench") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/studio/:tab/*" element={<Pieces />} />
          <Route path="/studio/workspace/:threadId" element={<p>the conversation</p>} />
        </Routes>
        <Address />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const address = () => screen.getByRole("status", { name: "address", hidden: true }).textContent;

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
    if (call === "GET /packages") return { body: [{ package_id: "bench", versions: [2, 1], thread_id: null }] };
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

test("a still shows its preview and tier, and turntable and variant cards are omitted", async () => {
  serve([turntable, still, variant]);
  show();
  expect(await screen.findByRole("img", { name: "Still of bench version 2" })).toHaveAttribute("src", still.preview);
  expect(screen.getByText("draft")).toBeInTheDocument();
  expect(screen.queryByRole("img", { name: /Turntable/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Walnut" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /viewer/ })).not.toBeInTheDocument();
});

test("a version with only a turntable shows no render card", async () => {
  serve([turntable]);
  show();
  expect(await screen.findByRole("link", { name: "Inspect version 2" })).toBeInTheDocument();
  expect(screen.queryByRole("img", { name: /Turntable/ })).not.toBeInTheDocument();
  expect(screen.queryByText("No renders of this version yet.")).not.toBeInTheDocument();
});

test("rating down with a comment is sent, shown and survives a reload of the list", async () => {
  const user = userEvent.setup();
  let stored: unknown = null;
  const calls = serve([still], (call) => {
    if (call === "PUT /packages/bench/versions/2/renders/still/feedback") {
      stored = { ...still, rating: "down", comment: "too dark" };
      return { body: stored };
    }
    if (call === "GET /packages/bench/versions/2/renders" && stored) return { body: [stored] };
  });
  show();
  await user.type(await screen.findByLabelText("Comment on Still"), "too dark");
  await user.click(screen.getByRole("button", { name: "Thumbs down Still" }));
  expect(await screen.findByRole("button", { name: "Thumbs down Still", pressed: true })).toBeInTheDocument();
  expect(calls.find(([m]) => m === "PUT")![2]).toEqual({ rating: "down", comment: "too dark" });
  expect(screen.getByLabelText("Comment on Still")).toHaveValue("too dark");
});

test("clearing a rating calls the API and unpresses the thumbs", async () => {
  const user = userEvent.setup();
  let cleared = false;
  const rated = { ...still, rating: "up", comment: "nice" };
  const calls = serve([rated], (call) => {
    if (call === "DELETE /packages/bench/versions/2/renders/still/feedback") {
      cleared = true;
      return { body: still };
    }
    if (call === "GET /packages/bench/versions/2/renders" && cleared) return { body: [still] };
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Clear rating of Still" }));
  expect(await screen.findByRole("button", { name: "Thumbs up Still", pressed: false })).toBeInTheDocument();
  expect(calls.some(([m]) => m === "DELETE")).toBe(true);
});

test("a refusal is shown beside the render it names and the optimistic rating is rolled back", async () => {
  const user = userEvent.setup();
  serve([still], (call) => {
    if (call.startsWith("PUT")) {
      return { status: 409, body: { detail: { failure_class: "no_render", reason: "the render does not exist yet, so it cannot be rated" } } };
    }
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Thumbs up Still" }));
  const message = await screen.findByText("the render does not exist yet, so it cannot be rated");
  expect(message.closest("section")).toHaveAccessibleName("Still");
  expect(screen.getByRole("button", { name: "Thumbs up Still", pressed: false })).toBeInTheDocument();
});

test("a render made before ratings existed says so and offers no thumbs", async () => {
  serve([legacy]);
  show();
  expect(await screen.findByText("Rendered before ratings existed — render it again to rate it.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Thumbs/ })).toBeNull();
});

test("no model, prompt, token or cost text appears on the page", async () => {
  serve([still]);
  show();
  await screen.findByRole("img", { name: "Still of bench version 2" });
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
  serve([still], (call) => {
    if (call === "GET /packages/bench/versions/1/renders") return { body: [] };
  });
  show();
  await screen.findByRole("img", { name: "Still of bench version 2" });
  await user.selectOptions(screen.getByRole("combobox", { name: "Versions of bench" }), "1");
  expect(await screen.findByText("No renders of this version yet.")).toBeInTheDocument();
});

test("the versions are a dropdown, newest first, each with its state", async () => {
  serve([turntable], (call) => {
    if (call === "GET /packages") return { body: [{ package_id: "bench", versions: [4, 3, 2, 1] }] };
    if (call === "GET /packages/bench/versions/4") return { body: info(4, 4) };
    if (call === "GET /packages/bench/versions/3") return { body: info(3, 4, "failed") };
    if (call === "GET /packages/bench/versions/2") return { body: info(2, 4, "running") };
    if (call === "GET /packages/bench/versions/4/renders") return { body: [] };
  });
  show();
  const versions = await screen.findByRole("combobox", { name: "Versions of bench" });
  expect(await screen.findByRole("option", { name: "Version 2 (building)" })).toBeInTheDocument();
  expect(within(versions).getAllByRole("option").map((o) => o.textContent)).toEqual([
    "Version 4 (approved)",
    "Version 3 (failed)",
    "Version 2 (building)",
    "Version 1",
  ]);
  expect(versions).toHaveValue("4");
  expect(screen.queryByRole("button", { name: /^Version \d/ })).toBeNull();
});

test("a built version is approved from the page and the badge shows without a reload", async () => {
  const user = userEvent.setup();
  const state = { approved: null as number | null };
  const calls = serve([turntable], undefined, state);
  show();
  expect(await screen.findByText("No version approved yet.")).toBeInTheDocument();
  await user.click(await screen.findByRole("button", { name: "Approve version 2" }));
  expect(await screen.findByText("Approved: version 2")).toBeInTheDocument();
  expect(within(screen.getByRole("dialog", { name: "bench" })).getByText("Approved")).toBeInTheDocument();
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
  expect(await screen.findByRole("option", { name: "Version 2 (building)" })).toBeInTheDocument();
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

test("unapproving a piece placed in an approved room shows the refusal next to the control", async () => {
  const user = userEvent.setup();
  const reason =
    "bench version 2 is placed in the approved room composition Wohnen version 2; unapprove Wohnen version 2 first";
  serve(
    [turntable],
    (call) => {
      if (call === "DELETE /packages/bench/versions/2/approval") {
        return { status: 409, body: { detail: { failure_class: "placed_in_approved_room", reason } } };
      }
    },
    { approved: 2 },
  );
  show();
  await user.click(await screen.findByRole("button", { name: "Unapprove version 2" }));
  const refusal = await screen.findByText(reason);
  expect(refusal.closest("[role=group]")).toHaveAccessibleName("Approval of bench version 2");
  expect(screen.getByText("Approved: version 2")).toBeInTheDocument();
});

test("the import template is offered with how to use it", async () => {
  serve([turntable]);
  show("/studio/pieces");
  const link = await screen.findByRole("link", { name: "Download the import template" });
  expect(link).toHaveAttribute("href", "/design-import/template");
  expect(link).toHaveAttribute("download", "import-template.json");
  expect(link).toHaveTextContent("Import template");
  expect(screen.queryByText(/give it to another AI chat to fill in/)).toBeNull();
  const user = userEvent.setup();
  const about = screen.getByRole("button", { name: "About pieces and the import template" });
  await user.click(about);
  expect(about).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("note")).toHaveTextContent(/give it to another AI chat to fill in/);
  expect(screen.getByRole("note")).toHaveTextContent(/Tell us what you think of a render/);
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("note")).toBeNull();
});

test("the button, the template link and its help share one row above the tiles (Pieces header fits)", async () => {
  serve([turntable]);
  show("/studio/pieces");
  const create = await screen.findByRole("button", { name: "Create A New Piece" });
  const row = create.parentElement!;
  expect(within(row).getByRole("link", { name: "Download the import template" })).toBeInTheDocument();
  expect(within(row).getByRole("button", { name: "About pieces and the import template" })).toBeInTheDocument();
  expect(row.compareDocumentPosition(screen.getByRole("list", { name: "Pieces" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
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
  const inspect = screen.getByRole("link", { name: "Inspect version 2" });
  expect(inspect).toHaveAttribute("href", "/pieces/bench/versions/2");
  expect(inspect).toHaveAttribute("data-slot", "button");
  const line = design.closest("p")!;
  expect(line).toHaveTextContent("Downloads: Design (JSON) · Bundle (ZIP)");
  expect(line).not.toContainElement(inspect);
});

test("a version still building offers the design but not the bundle", async () => {
  serve([turntable], undefined, { approved: null, status: "running" });
  show();
  expect(await screen.findByRole("link", { name: "Download design (version 2)" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Download bundle/ })).toBeNull();
  expect(screen.queryByRole("link", { name: /Inspect/ })).toBeNull();
});

test("an unassigned piece shows No room and is attached to a room, which a reload keeps", async () => {
  const user = userEvent.setup();
  let room: string | null = null;
  const calls = serve([turntable], (call) => {
    if (call === "GET /packages") return { body: [{ package_id: "bench", versions: [2, 1], room }] };
    if (call === "GET /rooms") return { body: [summary("Hall"), summary("Schlafzimmer")] };
    if (call === "PUT /packages/bench/room") {
      room = "Schlafzimmer";
      return { body: { package_id: "bench", room } };
    }
  });
  show();
  expect(await screen.findByText("No room", { selector: "span" })).toBeInTheDocument();
  await screen.findByRole("option", { name: "Schlafzimmer" });
  await user.selectOptions(screen.getByLabelText("Room of bench"), "Schlafzimmer");
  expect(await screen.findByText("Room: Schlafzimmer")).toBeInTheDocument();
  expect(calls.find(([m, u]) => m === "PUT" && u === "/packages/bench/room")![2]).toEqual({ room: "Schlafzimmer" });
  expect(screen.getByLabelText("Room of bench")).toHaveValue("Schlafzimmer");
});

test("choosing No room clears the piece's room", async () => {
  const user = userEvent.setup();
  let room: string | null = "Hall";
  const calls = serve([turntable], (call) => {
    if (call === "GET /packages") return { body: [{ package_id: "bench", versions: [2, 1], room }] };
    if (call === "GET /rooms") return { body: [summary("Hall")] };
    if (call === "PUT /packages/bench/room") {
      room = null;
      return { body: { package_id: "bench", room } };
    }
  });
  show();
  await user.selectOptions(await screen.findByLabelText("Room of bench"), "No room");
  expect(await screen.findByText("No room", { selector: "span" })).toBeInTheDocument();
  expect(calls.find(([m]) => m === "PUT")![2]).toEqual({ room: null });
});

test("a refusal from the room route is shown next to the piece and its room is unchanged", async () => {
  const user = userEvent.setup();
  serve([turntable], (call) => {
    if (call === "GET /packages") return { body: [{ package_id: "bench", versions: [2, 1], room: "Hall" }] };
    if (call === "GET /rooms") return { body: [summary("Hall"), summary("Attic")] };
    if (call === "PUT /packages/bench/room") {
      return { status: 422, body: { detail: { failure_class: "unknown_room", reason: "there is no room 'Attic' in the house file" } } };
    }
  });
  show();
  await screen.findByRole("option", { name: "Attic" });
  await user.selectOptions(screen.getByLabelText("Room of bench"), "Attic");
  const refusal = await screen.findByText("there is no room 'Attic' in the house file");
  expect(refusal.closest('[role="dialog"]')).toHaveAccessibleName("bench");
  expect(screen.getByText("Room: Hall")).toBeInTheDocument();
});

// --- pricing per approved version (app-check-2026-10-09) ----------------------------------

const complete = {
  id: "p1", package_id: "bench", version: 2, computed_at: "2026-10-08T09:00:00+00:00", total_cents: 18420, complete: true,
  result: {
    materials: {
      "oak-18": { sheet_count: 2, cost_cents: 12000, cuts: [{ part_id: "side", name: "Side", qty: 2, status: "covered" }] },
    },
    hardware: [{ id: "hinge", item: "Concealed hinge", qty: "4", cost_cents: 1600 }],
    unpriced: [],
  },
};
const incomplete = {
  ...complete, id: "p0", computed_at: "2026-10-07T09:00:00+00:00", total_cents: 16800, complete: false,
  result: { ...complete.result, unpriced: [{ kind: "banding", label: "Oak edge banding", key: "band:oak", reason: "no price-list entry" }] },
};

async function openPricing(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByText("Pricing"));
}

test("an approved version lists its pricing with sheets, cuts, hardware and the total", async () => {
  const user = userEvent.setup();
  serve([], (call) => (call === "GET /packages/bench/versions/2/pricings" ? { body: [complete] } : undefined), { approved: 2 });
  show();
  await openPricing(user);
  expect(await screen.findByText("Total: 184,20 €")).toBeInTheDocument();
  expect(screen.getByText("oak-18: 2 sheets, 120,00 €")).toBeInTheDocument();
  expect(screen.getByText("2 × Side (oak-18, covered)")).toBeInTheDocument();
  expect(screen.getByText("4 × Concealed hinge: 16,00 €")).toBeInTheDocument();
  expect(screen.queryByText("Pricing incomplete")).not.toBeInTheDocument();
  expect(screen.queryByText(/GPU|token|model/i)).not.toBeInTheDocument();
});

test("an incomplete pricing says so and names the unpriced line", async () => {
  const user = userEvent.setup();
  serve([], (call) => (call === "GET /packages/bench/versions/2/pricings" ? { body: [incomplete] } : undefined), { approved: 2 });
  show();
  await openPricing(user);
  expect(await screen.findByText("Pricing incomplete")).toBeInTheDocument();
  expect(screen.getByText("Oak edge banding: no price-list entry")).toBeInTheDocument();
});

test("pricing a version lists the new pricing first and selects it", async () => {
  const user = userEvent.setup();
  const calls = serve([], (call) => {
    if (call === "GET /packages/bench/versions/2/pricings") return { body: [incomplete] };
    if (call === "POST /packages/bench/versions/2/pricings") return { status: 201, body: complete };
  }, { approved: 2 });
  show();
  await openPricing(user);
  await screen.findByText("Pricing incomplete");
  await user.click(screen.getByRole("button", { name: "Price this version" }));
  expect(await screen.findByText("Total: 184,20 €")).toBeInTheDocument();
  const options = screen.getAllByRole("option").filter((o) => /€/.test(o.textContent ?? ""));
  expect(options[0]).toHaveTextContent("184,20 €");
  expect(screen.getByLabelText("Pricings of bench version 2")).toHaveValue("p1");
  expect(calls.find(([m, url]) => m === "POST" && url.endsWith("/pricings"))![2]).toEqual({});
});

test("a refused pricing shows its reason next to the action", async () => {
  const user = userEvent.setup();
  serve([], (call) => {
    if (call === "GET /packages/bench/versions/2/pricings") return { body: [] };
    if (call === "POST /packages/bench/versions/2/pricings")
      return { status: 422, body: { detail: { failure_class: "refused", reason: "the cut list cannot be read" } } };
  }, { approved: 2 });
  show();
  await openPricing(user);
  await user.click(await screen.findByRole("button", { name: "Price this version" }));
  expect(await screen.findByText("the cut list cannot be read")).toBeInTheDocument();
});

test("a version that is not approved must be approved before it is priced", async () => {
  const user = userEvent.setup();
  const calls = serve([], undefined, { approved: 1 });
  show();
  await openPricing(user);
  expect(await screen.findByText("Version 2 must be approved before it can be priced.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Price this version" })).not.toBeInTheDocument();
  expect(calls.some(([, url]) => url.endsWith("/pricings"))).toBe(false);
});

// --- deleting a version (version-cleanup-and-inspection) ---------------------------------

test("a confirmed delete drops the version from the piece and shows another", async () => {
  const user = userEvent.setup();
  const listed = [2, 1];
  const calls = serve([turntable], (call) => {
    if (call === "GET /packages") return { body: [{ package_id: "bench", versions: [...listed] }] };
    if (call === "GET /packages/bench/versions/1/renders") return { body: [] };
    if (call === "DELETE /packages/bench/versions/2") {
      listed.splice(0, 1);
      return { status: 204 };
    }
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Delete version 2" }));
  expect(calls.some(([m, u]) => m === "DELETE" && u === "/packages/bench/versions/2")).toBe(false);
  await user.click(screen.getByRole("button", { name: "Yes, delete version 2" }));
  expect(await screen.findByText("No renders of this version yet.")).toBeInTheDocument();
  const versions = screen.getByRole("combobox", { name: "Versions of bench" });
  expect(versions).not.toHaveTextContent("Version 2");
  expect(versions).toHaveValue("1");
});

test("an approved version offers no delete", async () => {
  serve([turntable], undefined, { approved: 2 });
  show();
  expect(await screen.findByText("Approved: version 2")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Delete version 2" })).toBeNull();
});

test("deleting the only version says the piece goes and drops the piece", async () => {
  const user = userEvent.setup();
  let gone = false;
  serve([turntable], (call) => {
    if (call === "GET /packages") return { body: gone ? [] : [{ package_id: "bench", versions: [2] }] };
    if (call === "DELETE /packages/bench/versions/2") {
      gone = true;
      return { status: 204 };
    }
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Delete version 2" }));
  expect(screen.getByText(/the whole piece will be deleted/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Yes, delete version 2" }));
  expect(await screen.findByText("No pieces yet. Use Create A New Piece to start a conversation and describe one.")).toBeInTheDocument();
});

// --- piece conversations (piece-conversation-link) ---------------------------------------

test("Create A New Piece sits above the tiles, starts an unbound conversation and opens it", async () => {
  const user = userEvent.setup();
  const calls = serve([turntable], (call) => {
    if (call === "GET /packages") {
      return {
        body: [
          { package_id: "bench", versions: [2, 1], thread_id: null },
          { package_id: "shelf", versions: [1], thread_id: null },
        ],
      };
    }
    if (call === "POST /chat/threads") {
      return {
        status: 201,
        body: { thread_id: "t-new", title: "", package_id: null, created_at: "", last_turn_at: "" },
      };
    }
  });
  show("/studio/pieces");
  const create = await screen.findByRole("button", { name: "Create A New Piece" });
  const firstCard = await screen.findByRole("button", { name: "bench" });
  expect(create.compareDocumentPosition(firstCard) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  await user.click(create);
  expect(await screen.findByText("the conversation")).toBeInTheDocument();
  expect(calls).toContainEqual(["POST", "/chat/threads", {}]);
});

test("Open conversation links to the piece's existing thread", async () => {
  serve([turntable], (call) => {
    if (call === "GET /packages") {
      return { body: [{ package_id: "bench", versions: [2, 1], thread_id: "t-bench" }] };
    }
  });
  show();
  const card = await screen.findByRole("dialog", { name: "bench" });
  const link = within(card).getByRole("link", { name: "Open conversation" });
  expect(link).toHaveAttribute("href", "/studio/workspace/t-bench");
});

test("Start conversation binds the piece and opens the new thread", async () => {
  const user = userEvent.setup();
  const calls = serve([turntable], (call) => {
    if (call === "POST /chat/threads") {
      return {
        status: 201,
        body: { thread_id: "t-bound", title: "", package_id: "bench", created_at: "", last_turn_at: "" },
      };
    }
  });
  show();
  const card = await screen.findByRole("dialog", { name: "bench" });
  await user.click(within(card).getByRole("button", { name: "Start conversation" }));
  expect(await screen.findByText("the conversation")).toBeInTheDocument();
  expect(calls).toContainEqual(["POST", "/chat/threads", { package_id: "bench" }]);
});

test("a refused start shows the reason next to the piece", async () => {
  const user = userEvent.setup();
  serve([turntable], (call) => {
    if (call === "POST /chat/threads") {
      return {
        status: 409,
        body: {
          detail: {
            failure_class: "piece_has_conversation",
            reason: "hall-bench already has a conversation; open that one instead of starting another",
          },
        },
      };
    }
  });
  show();
  const card = await screen.findByRole("dialog", { name: "bench" });
  await user.click(within(card).getByRole("button", { name: "Start conversation" }));
  expect(
    await within(card).findByText("hall-bench already has a conversation; open that one instead of starting another"),
  ).toBeInTheDocument();
  expect(screen.queryByText("the conversation")).not.toBeInTheDocument();
});

// --- the piece's picture (pieces-page-and-chat-scroll) -----------------------------------

test("the card shows the newest screenshot, keeps it when another version is chosen, and moves to an approved one", async () => {
  const user = userEvent.setup();
  const state = { approved: null as number | null };
  const built = (version: number) => ({ ...info(version, state.approved), files: ["screenshot.png", "still.png"] });
  serve([turntable], (call) => {
    const read = /^GET \/packages\/bench\/versions\/(\d)$/.exec(call);
    if (read) return { body: built(Number(read[1])) };
    if (call === "GET /packages/bench/versions/1/renders") return { body: [] };
    if (call === "PUT /packages/bench/versions/1/approval") {
      state.approved = 1;
      return { body: built(1) };
    }
  }, state);
  show();
  const picture = await screen.findByRole("img", { name: "bench version 2" });
  expect(picture).toHaveAttribute("src", "/packages/bench/versions/2/files/screenshot.png");
  expect(picture.closest("figure")).toHaveTextContent("Version 2");
  await user.selectOptions(screen.getByRole("combobox", { name: "Versions of bench" }), "1");
  expect(await screen.findByText("No renders of this version yet.")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "bench version 2" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Approve version 1" }));
  const approved = await screen.findByRole("img", { name: "bench version 1" });
  expect(approved).toHaveAttribute("src", "/packages/bench/versions/1/files/screenshot.png");
  expect(approved.closest("figure")).toHaveTextContent("Version 1 (approved)");
});

test("a piece with no screenshot shows no picture", async () => {
  serve([turntable], undefined, { approved: null, status: "running" });
  show();
  expect(await screen.findByRole("dialog", { name: "bench" })).toBeInTheDocument();
  expect(screen.queryByRole("img", { name: /^bench version/ })).toBeNull();
  expect(screen.queryByRole("figure")).toBeNull();
});

// --- tiles and the dialog (studio-tile-grid) ---------------------------------------------

function twoPieces(path: string, extra: (call: string) => { status?: number; body?: unknown } | undefined = () => undefined) {
  const built = (version: number, approved: number | null) => ({ ...info(version, approved), files: ["screenshot.png"] });
  const state = { approved: 1 as number | null };
  serve([still], (call) => {
    const mine = extra(call);
    if (mine) return mine;
    if (call === "GET /packages") {
      return {
        body: [
          { package_id: "bench", versions: [2, 1], thread_id: null, room: null },
          { package_id: "shelf", versions: [1], thread_id: null, room: null },
        ],
      };
    }
    const read = /^GET \/packages\/bench\/versions\/(\d)$/.exec(call);
    if (read) return { body: built(Number(read[1]), state.approved) };
    if (call === "GET /packages/shelf/versions/1") return { body: { package_id: "shelf", version: 1, status: "running", approved_at: null } };
    if (call === "PUT /packages/bench/versions/2/approval") {
      state.approved = 2;
      return { body: built(2, 2) };
    }
  }, state);
  show(path);
}

test("each piece is a tile with its picture, caption and approval badge", async () => {
  twoPieces("/studio/pieces");
  const bench = await screen.findByRole("button", { name: "bench" });
  await within(bench).findByText("Version 1 (approved)");
  expect(bench.querySelector("img")).toHaveAttribute("src", "/packages/bench/versions/1/files/screenshot.png");
  expect(within(bench).getByText("Approved")).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("a piece with no screenshot shows a placeholder tile and no error (No screenshot at all)", async () => {
  twoPieces("/studio/pieces");
  const shelf = await screen.findByRole("button", { name: "shelf" });
  expect(within(shelf).getByTestId("tile-placeholder")).toBeInTheDocument();
  expect(shelf.querySelector("img")).toBeNull();
  expect(screen.queryByRole("alert")).toBeNull();
});

test("choosing a tile opens its dialog at its own address, keeping the page (Open a piece)", async () => {
  const user = userEvent.setup();
  twoPieces("/studio/pieces?page=1");
  await user.click(await screen.findByRole("button", { name: "bench" }));
  expect(address()).toBe("/studio/pieces/bench?page=1");
  const dialog = await screen.findByRole("dialog", { name: "bench" });
  expect(within(dialog).getByRole("button", { name: "Start conversation" })).toBeInTheDocument();
  expect(within(dialog).getByRole("combobox", { name: "Versions of bench" })).toBeInTheDocument();
  expect(within(dialog).getByRole("combobox", { name: "Room of bench" })).toBeInTheDocument();
  expect(await within(dialog).findByRole("img", { name: "Still of bench version 2" })).toBeInTheDocument();
});

test("closing a dialog opened from the grid goes back to the grid's address (Back closes)", async () => {
  const user = userEvent.setup();
  twoPieces("/studio/pieces?page=1");
  await user.click(await screen.findByRole("button", { name: "bench" }));
  await screen.findByRole("dialog", { name: "bench" });
  await user.keyboard("{Escape}");
  expect(address()).toBe("/studio/pieces?page=1");
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.getByRole("button", { name: "bench" })).toHaveFocus();
});

test("a dialog address reached directly opens the dialog, and closing it shows the grid", async () => {
  const user = userEvent.setup();
  twoPieces("/studio/pieces/bench");
  expect(await screen.findByRole("dialog", { name: "bench" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Close" }));
  expect(address()).toBe("/studio/pieces");
  expect(screen.getByRole("button", { name: "bench" })).toBeInTheDocument();
});

test("an address naming no piece shows the grid and no dialog (Unknown item)", async () => {
  twoPieces("/studio/pieces/murphy-bed");
  expect(await screen.findByRole("button", { name: "bench" })).toBeInTheDocument();
  await waitFor(() => expect(address()).toBe("/studio/pieces"));
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("approving in the dialog moves the tile's picture without a reload (Approval changes the tile)", async () => {
  const user = userEvent.setup();
  twoPieces("/studio/pieces/bench");
  const dialog = await screen.findByRole("dialog", { name: "bench" });
  await user.click(await within(dialog).findByRole("button", { name: "Approve version 2" }));
  await user.keyboard("{Escape}");
  const bench = screen.getByRole("button", { name: "bench" });
  expect(await within(bench).findByText("Version 2 (approved)")).toBeInTheDocument();
  expect(bench.querySelector("img")).toHaveAttribute("src", "/packages/bench/versions/2/files/screenshot.png");
});
