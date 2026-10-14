import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import ModelLibrary from "./ModelLibrary";

const armchair = {
  model_id: "m1", name: "Armchair", kind: "glb", width_mm: 800, depth_mm: 700, height_mm: 900,
  state: "checking", reason: null,
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ModelLibrary /></QueryClientProvider>);
}

test("each model is a card with its size, state and a delete action", async () => {
  stubFetch((call) => {
    if (call === "GET /models") return { body: [{ ...armchair, name: "Sofa", width_mm: 2200, depth_mm: 950, height_mm: 800, state: "ready" }] };
  });
  show();
  const card = within(await screen.findByRole("region", { name: "Sofa" }));
  expect(card.getByRole("heading", { level: 2, name: "Sofa" })).toBeInTheDocument();
  expect(card.getByText("2200 × 950 × 800 mm")).toBeInTheDocument();
  expect(card.getByText("ready")).toBeInTheDocument();
  expect(card.getByRole("button", { name: "Delete Sofa" })).toBeInTheDocument();
});

test("an empty library says so", async () => {
  stubFetch((call) => (call === "GET /models" ? { body: [] } : undefined));
  show();
  expect(await screen.findByText("No models yet.")).toBeInTheDocument();
});

test("a refused upload shows its reason and leaves the library unchanged", async () => {
  // A file picker's filter can be overridden by the owner, so the service decides.
  const user = userEvent.setup({ applyAccept: false });
  stubFetch((call) => {
    if (call === "GET /models") return { body: [] };
    if (call === "POST /models") {
      return { status: 415, body: { detail: { failure_class: "unsupported_type", reason: "a .blend file is not accepted; export the model as GLB, glTF or OBJ" } } };
    }
  });
  show();
  await user.upload(await screen.findByLabelText("File"), new File(["BLENDER"], "chair.blend"));
  await user.type(screen.getByLabelText("Name"), "Chair");
  await user.type(screen.getByLabelText("Width (mm)"), "800");
  await user.type(screen.getByLabelText("Depth (mm)"), "700");
  await user.type(screen.getByLabelText("Height (mm)"), "900");
  await user.click(screen.getByRole("button", { name: "Upload model" }));
  expect(await screen.findByText("a .blend file is not accepted; export the model as GLB, glTF or OBJ")).toBeInTheDocument();
  expect(screen.getByText("No models yet.")).toBeInTheDocument();
});

test("a model being checked turns ready without a reload", async () => {
  let checked = false;
  stubFetch((call) => {
    if (call === "GET /models") {
      const body = [{ ...armchair, state: checked ? "ready" : "checking" }];
      checked = true;
      return { body };
    }
  });
  show();
  const card = within(await screen.findByRole("region", { name: "Armchair" }));
  expect(card.getByText("checking")).toBeInTheDocument();
  await waitFor(() => expect(card.getByText("ready")).toBeInTheDocument(), { timeout: 4000 });
});

test("no rooms, compositions, model name, prompt, token or cost text appears on the page", async () => {
  const calls = stubFetch((call) => (call === "GET /models" ? { body: [{ ...armchair, state: "ready" }] } : undefined));
  show();
  await screen.findByRole("region", { name: "Armchair" });
  expect(calls.map(([, url]) => url)).not.toContain("/rooms");
  expect(calls.map(([, url]) => url)).not.toContain("/compositions");
  const text = document.body.textContent ?? "";
  for (const word of [/deepseek/i, /prompt/i, /token/i, /€|eur\b/i, /\bcost/i]) {
    expect(text).not.toMatch(word);
  }
});
