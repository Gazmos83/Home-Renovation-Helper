import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import Rooms from "./Rooms";

const wohnen = {
  scope: "room", name: "Wohnen", slug: "wohnen", latest_version: 2, status: "succeeded",
  items: [
    { id: "wall", type: "piece", name: "listening-wall v4", version: 4, approved: false, no_longer_approved: true },
    { id: "sofa", type: "stand-in", name: "Sofa" },
  ],
  picture: "/compositions/wohnen/versions/2/files/screenshot.png",
  viewer: "/compositions/wohnen/versions/2/files/viewer.html",
};
const armchair = {
  model_id: "m1", name: "Armchair", kind: "glb", width_mm: 800, depth_mm: 700, height_mm: 900,
  state: "checking", reason: null,
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Rooms /></QueryClientProvider>);
}

test("a placed piece that is no longer approved is marked plainly", async () => {
  stubFetch((call) => {
    if (call === "GET /compositions") return { body: [wohnen] };
    if (call === "GET /models") return { body: [] };
  });
  show();
  const card = within(await screen.findByRole("region", { name: "Wohnen" }));
  expect(card.getByText("listening-wall v4").closest("li")).toHaveTextContent("no longer approved");
  expect(card.getByText("Sofa").closest("li")).not.toHaveTextContent("no longer approved");
  expect(card.getByRole("img")).toHaveAttribute("src", wohnen.picture);
  expect(card.getByRole("link", { name: "Open the turntable viewer of Wohnen" })).toHaveAttribute("href", wohnen.viewer);
});

test("a refused upload shows its reason and leaves the library unchanged", async () => {
  // A file picker's filter can be overridden by the owner, so the service decides.
  const user = userEvent.setup({ applyAccept: false });
  stubFetch((call) => {
    if (call === "GET /compositions") return { body: [] };
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
    if (call === "GET /compositions") return { body: [] };
    if (call === "GET /models") {
      const body = [{ ...armchair, state: checked ? "ready" : "checking" }];
      checked = true;
      return { body };
    }
  });
  show();
  const library = within(await screen.findByRole("region", { name: "Model library" }));
  expect(await library.findByText("checking")).toBeInTheDocument();
  await waitFor(() => expect(library.getByText("ready")).toBeInTheDocument(), { timeout: 4000 });
});

test("no model name, prompt, token or cost text appears on the page", async () => {
  stubFetch((call) => {
    if (call === "GET /compositions") return { body: [wohnen] };
    if (call === "GET /models") return { body: [{ ...armchair, state: "ready" }] };
  });
  show();
  await screen.findByRole("region", { name: "Wohnen" });
  const text = document.body.textContent ?? "";
  for (const word of [/deepseek/i, /prompt/i, /token/i, /€|eur\b/i, /\bcost/i]) {
    expect(text).not.toMatch(word);
  }
});
