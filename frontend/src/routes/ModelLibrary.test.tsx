import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { drawModel } from "../lib/modelThumbnail";
import { stubFetch } from "../test/fetchStub";
import ModelLibrary from "./ModelLibrary";

// No WebGL in jsdom: drawing a preview picture is stubbed; each test says whether it works.
vi.mock("../lib/modelThumbnail", () => ({ drawModel: vi.fn() }));
const draw = vi.mocked(drawModel);
beforeEach(() => {
  draw.mockReset();
  draw.mockRejectedValue(new Error("no WebGL"));
});

const armchair = {
  model_id: "m1", name: "Armchair", kind: "glb", width_mm: 800, depth_mm: 700, height_mm: 900,
  state: "checking", reason: null, measured_mm: null, triangles: null, entry: "model.glb", has_thumbnail: false,
};
const sofa = {
  ...armchair, model_id: "m2", name: "Sofa", width_mm: 2200, depth_mm: 950, height_mm: 800, state: "ready",
  measured_mm: { x: 2210.4, y: 948, z: 801 }, triangles: 40000, has_thumbnail: true,
};

function Address() {
  const location = useLocation();
  return <output aria-label="address">{location.pathname + location.search}</output>;
}

/** The Model Library tab at `path`: Uploaded models, a model's dialog, or the upload dialog. */
function show(path = "/studio/models") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/studio/:tab/*" element={<ModelLibrary />} />
        </Routes>
        <Address />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const address = () => screen.getByRole("status", { name: "address", hidden: true }).textContent;

test("each model is a tile with its picture, size and state (Models listed)", async () => {
  stubFetch((call) => (call === "GET /models" ? { body: [sofa, armchair] } : undefined));
  show();
  const tile = await screen.findByRole("button", { name: "Sofa" });
  expect(tile.querySelector("img")).toHaveAttribute("src", "/models/m2/thumbnail");
  expect(within(tile).getByText("2200 × 950 × 800 mm")).toBeInTheDocument();
  expect(within(tile).getByText("ready")).toBeInTheDocument();
  const waiting = screen.getByRole("button", { name: "Armchair" });
  expect(within(waiting).getByTestId("tile-placeholder")).toBeInTheDocument();
  expect(within(waiting).getByText("checking")).toBeInTheDocument();
});

test("a tile opens the model's dialog with its picture, sizes, state and delete", async () => {
  const user = userEvent.setup();
  stubFetch((call) => (call === "GET /models" ? { body: [sofa] } : undefined));
  show();
  await user.click(await screen.findByRole("button", { name: "Sofa" }));
  expect(address()).toBe("/studio/models/m2");
  const dialog = within(await screen.findByRole("dialog", { name: "Sofa" }));
  expect(dialog.getByRole("img", { name: "Picture of Sofa" })).toHaveAttribute("src", "/models/m2/thumbnail");
  expect(dialog.getByText("Stated size: 2200 × 950 × 800 mm")).toBeInTheDocument();
  expect(dialog.getByText("Measured: 2210 × 948 × 801 mm, 40000 triangles")).toBeInTheDocument();
  expect(dialog.getByText("ready")).toBeInTheDocument();
  expect(dialog.getByRole("button", { name: "Delete Sofa" })).toBeInTheDocument();
});

test("a refused model shows its state as an error and its reason", async () => {
  const lamp = { ...armchair, model_id: "m3", name: "Lamp", state: "refused", reason: "the model has no mesh" };
  stubFetch((call) => (call === "GET /models" ? { body: [lamp] } : undefined));
  show("/studio/models/m3");
  const dialog = within(await screen.findByRole("dialog", { name: "Lamp" }));
  expect(dialog.getByText("refused")).toHaveClass("bg-destructive");
  expect(dialog.getByText("the model has no mesh")).toBeInTheDocument();
  expect(within(screen.getByRole("button", { name: "Lamp", hidden: true })).getByText("refused")).toHaveClass("bg-destructive");
});

test("a deleted model's dialog closes and its tile is gone", async () => {
  const user = userEvent.setup();
  let models = [sofa];
  stubFetch((call) => {
    if (call === "GET /models") return { body: models };
    if (call === "DELETE /models/m2") {
      models = [];
      return { status: 204 };
    }
  });
  show("/studio/models/m2");
  await user.click(await screen.findByRole("button", { name: "Delete Sofa" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(screen.queryByRole("button", { name: "Sofa" })).toBeNull();
  expect(screen.getByText("No models yet. Choose Upload model to add one.")).toBeInTheDocument();
  expect(address()).toBe("/studio/models");
});

test("a refused delete is shown in the dialog and the model stays", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /models") return { body: [sofa] };
    if (call === "DELETE /models/m2") {
      return { status: 409, body: { detail: { failure_class: "in_use", reason: "'Sofa' is placed in Wohnen v2; remove it there first" } } };
    }
  });
  show("/studio/models/m2");
  await user.click(await screen.findByRole("button", { name: "Delete Sofa" }));
  const dialog = screen.getByRole("dialog", { name: "Sofa" });
  expect(await within(dialog).findByText("'Sofa' is placed in Wohnen v2; remove it there first")).toBeInTheDocument();
});

test("an empty library says so and points to Upload model", async () => {
  stubFetch((call) => (call === "GET /models" ? { body: [] } : undefined));
  show();
  expect(await screen.findByText("No models yet. Choose Upload model to add one.")).toBeInTheDocument();
  expect(screen.queryByRole("list")).toBeNull();
});

test("Upload model is a dialog over the grid (Upload in a dialog)", async () => {
  stubFetch((call) => (call === "GET /models" ? { body: [sofa] } : undefined));
  show("/studio/models/upload");
  const dialog = within(await screen.findByRole("dialog", { name: "Upload a model" }));
  expect(dialog.getByRole("form", { name: "Upload a model" })).toBeInTheDocument();
  expect(dialog.getByLabelText("File")).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Sofa", hidden: true })).toBeInTheDocument();
});

async function fillIn(user: ReturnType<typeof userEvent.setup>, file: File) {
  await user.upload(await screen.findByLabelText("File"), file);
  await user.type(screen.getByLabelText("Name"), "Chair");
  await user.type(screen.getByLabelText("Width (mm)"), "800");
  await user.type(screen.getByLabelText("Depth (mm)"), "700");
  await user.type(screen.getByLabelText("Height (mm)"), "900");
  await user.click(screen.getByRole("button", { name: "Upload model" }));
}

test("a refused upload keeps the dialog and what was typed, and the library is unchanged (Upload refused)", async () => {
  // A file picker's filter can be overridden by the owner, so the service decides.
  const user = userEvent.setup({ applyAccept: false });
  stubFetch((call) => {
    if (call === "GET /models") return { body: [] };
    if (call === "POST /models") {
      return { status: 415, body: { detail: { failure_class: "unsupported_type", reason: "a .blend file is not accepted; export the model as GLB, glTF or OBJ" } } };
    }
  });
  show("/studio/models/upload");
  await fillIn(user, new File(["BLENDER"], "chair.blend"));
  const dialog = within(screen.getByRole("dialog", { name: "Upload a model" }));
  expect(await dialog.findByText("a .blend file is not accepted; export the model as GLB, glTF or OBJ")).toBeInTheDocument();
  expect(dialog.getByLabelText("Name")).toHaveValue("Chair");
  expect(address()).toBe("/studio/models/upload");
  expect(screen.getByText("No models yet. Choose Upload model to add one.")).toBeInTheDocument();
});

test("a successful upload closes the dialog and shows the new model checking on its page (Upload succeeds)", async () => {
  const user = userEvent.setup();
  const others = Array.from({ length: 16 }, (_, i) => ({ ...sofa, model_id: `o${i}`, name: `Model ${i}` }));
  let listed: unknown[] = others;
  const chair = { ...armchair, model_id: "m9", name: "Chair" };
  stubFetch((call) => {
    if (call === "GET /models") return { body: listed };
    if (call === "POST /models") {
      listed = [...others, chair];
      return { status: 201, body: chair };
    }
  });
  show("/studio/models/upload");
  await fillIn(user, new File(["glTF"], "chair.glb"));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(address()).toBe("/studio/models?page=2");
  const tile = await screen.findByRole("button", { name: "Chair" });
  expect(within(tile).getByText("checking")).toBeInTheDocument();
  expect(within(tile).getByTestId("tile-placeholder")).toBeInTheDocument();
});

test("a model being checked turns ready and gets its preview picture without a reload (Check finishes)", async () => {
  draw.mockResolvedValue(new Blob(["png"], { type: "image/png" }));
  let checked = false;
  let pictured = false;
  const calls = stubFetch((call) => {
    if (call === "GET /models") {
      const body = [{ ...armchair, state: checked ? "ready" : "checking", has_thumbnail: pictured }];
      checked = true;
      return { body };
    }
    if (call === "PUT /models/m1/thumbnail") {
      pictured = true;
      return { status: 204 };
    }
  });
  show();
  const tile = within(await screen.findByRole("button", { name: "Armchair" }));
  expect(tile.getByText("checking")).toBeInTheDocument();
  expect(tile.getByTestId("tile-placeholder")).toBeInTheDocument();
  await waitFor(() => expect(tile.getByText("ready")).toBeInTheDocument(), { timeout: 4000 });
  await waitFor(() => expect(screen.getByRole("button", { name: "Armchair" }).querySelector("img")).toHaveAttribute("src", "/models/m1/thumbnail"));
  expect(draw).toHaveBeenCalledTimes(1);
  expect(draw.mock.calls[0][0]).toMatchObject({ model_id: "m1", entry: "model.glb" });
  const put = calls.find(([method, url]) => method === "PUT" && url === "/models/m1/thumbnail");
  expect(put?.[2]).toBeInstanceOf(Blob);
});

test("a model that cannot be drawn keeps its placeholder, shows no error and is not tried again (Preview cannot be drawn)", async () => {
  const ready = [{ ...armchair, state: "ready" }, { ...armchair, model_id: "m4", name: "Stool", state: "ready" }];
  const calls = stubFetch((call) => (call === "GET /models" ? { body: ready } : undefined));
  show();
  await waitFor(() => expect(draw).toHaveBeenCalledTimes(2));
  expect(draw.mock.calls.map(([model]) => model.model_id)).toEqual(["m1", "m4"]);
  for (const name of ["Armchair", "Stool"]) {
    expect(within(screen.getByRole("button", { name })).getByTestId("tile-placeholder")).toBeInTheDocument();
  }
  expect(screen.queryByRole("alert")).toBeNull();
  expect(calls.some(([method]) => method === "PUT")).toBe(false);
  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(draw).toHaveBeenCalledTimes(2);
});

test("a model with a picture, or not ready, is not drawn", async () => {
  stubFetch((call) => (call === "GET /models" ? { body: [sofa, armchair] } : undefined));
  show();
  await screen.findByRole("button", { name: "Sofa" });
  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(draw).not.toHaveBeenCalled();
});

test("an address naming no model shows the grid and no dialog (Unknown item)", async () => {
  stubFetch((call) => (call === "GET /models" ? { body: [sofa] } : undefined));
  show("/studio/models/deleted-id");
  expect(await screen.findByRole("button", { name: "Sofa" })).toBeInTheDocument();
  await waitFor(() => expect(address()).toBe("/studio/models"));
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("no rooms, compositions, model name, prompt, token or cost text appears on the page", async () => {
  const calls = stubFetch((call) => (call === "GET /models" ? { body: [{ ...armchair, state: "ready" }] } : undefined));
  show();
  await screen.findByRole("button", { name: "Armchair" });
  expect(calls.map(([, url]) => url)).not.toContain("/rooms");
  expect(calls.map(([, url]) => url)).not.toContain("/compositions");
  const text = document.body.textContent ?? "";
  for (const word of [/deepseek/i, /prompt/i, /token/i, /€|eur\b/i, /\bcost/i]) {
    expect(text).not.toMatch(word);
  }
});
