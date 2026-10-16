import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { stubFetch } from "../test/fetchStub";
import Help from "./Help";

const PROMPT = "You are a furniture designer. Return the whole document as JSON alone, with no other text before or after it.";
const STEPS = ["You describe the piece you want.", "Intake confirms the room and the numbers.", "The Designer drafts the piece, or imports your design file.", "A final render runs after you type \"yes\"."];

const HELP = {
  topics: [
    {
      id: "blueprint",
      title: "Preparing a blueprint or a sketch",
      body: [
        { text: "Intake reads a plan or a hand sketch and turns it into rooms." },
        { heading: "The measurements Intake needs", items: ["Each room's name.", "The ceiling height.", "The wall thickness."] },
      ],
    },
    {
      id: "files",
      title: "Files a conversation accepts",
      body: [
        {
          items: [
            "Plans and photos: PNG or JPEG images.",
            "Notes: Markdown (.md) or plain text (.txt).",
            "Designs: a design file (.json) exported from a piece or made from the import template.",
          ],
        },
      ],
    },
    {
      id: "template",
      title: "Designing from a photo with the design file template",
      download: "import_template",
      body: [{ heading: "How to use the template", items: ["Download the import template below."] }],
      prompt: PROMPT,
    },
    { id: "workflow", title: "How a piece is made", body: [{ text: "Every piece follows the same path." }, { heading: "The steps", items: STEPS }] },
  ],
};

afterEach(() => vi.unstubAllGlobals());

function renderHelp(reply: { status?: number; body?: unknown } = { body: HELP }) {
  const calls = stubFetch((call) => (call === "GET /help" ? reply : undefined));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Help />
    </QueryClientProvider>,
  );
  return calls;
}

const topic = (title: string) => screen.getByText(title).closest("details") as HTMLDetailsElement;

test("every topic starts collapsed, showing its title only", async () => {
  renderHelp();
  await screen.findByText("Preparing a blueprint or a sketch");
  for (const title of HELP.topics.map((t) => t.title)) {
    expect(topic(title).open).toBe(false);
  }
  expect(screen.getByText("The wall thickness.")).not.toBeVisible();
});

test("expanding the blueprint topic lists the measurements and leaves the others collapsed", async () => {
  const user = userEvent.setup();
  renderHelp();
  await user.click(await screen.findByText("Preparing a blueprint or a sketch"));
  const blueprint = within(topic("Preparing a blueprint or a sketch"));
  expect(topic("Preparing a blueprint or a sketch").open).toBe(true);
  expect(blueprint.getByText("The wall thickness.")).toBeVisible();
  expect(blueprint.getByRole("img", { name: /Example: a hall/ })).toBeInTheDocument();
  expect(topic("Files a conversation accepts").open).toBe(false);
});

test("the files topic names images, notes and design files", async () => {
  renderHelp();
  await screen.findByText("Files a conversation accepts");
  const files = within(topic("Files a conversation accepts"));
  expect(files.getByText(/PNG or JPEG/)).toBeInTheDocument();
  expect(files.getByText(/Markdown \(\.md\) or plain text/)).toBeInTheDocument();
  expect(files.getByText(/design file \(\.json\)/)).toBeInTheDocument();
});

test("the template topic downloads the import template from the owner-gated route", async () => {
  renderHelp();
  await screen.findByText("Designing from a photo with the design file template");
  const link = within(topic("Designing from a photo with the design file template")).getByRole("link", {
    name: "Download the import template",
    hidden: true,
  });
  expect(link).toHaveAttribute("href", "/design-import/template");
  expect(link).toHaveAttribute("download", "import-template.json");
});

test("Copy puts the exact prompt on the clipboard and confirms it", async () => {
  const user = userEvent.setup();
  const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
  renderHelp();
  await user.click(await screen.findByText("Designing from a photo with the design file template"));
  await user.click(screen.getByRole("button", { name: "Copy prompt" }));
  expect(writeText).toHaveBeenCalledWith(PROMPT);
  expect(await screen.findByRole("button", { name: "Copied" })).toBeInTheDocument();
});

test("a failed copy says to select the text", async () => {
  const user = userEvent.setup();
  vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("denied"));
  renderHelp();
  await user.click(await screen.findByText("Designing from a photo with the design file template"));
  await user.click(screen.getByRole("button", { name: "Copy prompt" }));
  expect(await screen.findByText("Copy failed — select the text.")).toBeInTheDocument();
});

test("the workflow diagram's accessible name names every step and the template branch", async () => {
  const user = userEvent.setup();
  renderHelp();
  await user.click(await screen.findByText("How a piece is made"));
  const diagram = within(topic("How a piece is made")).getByRole("img");
  const name = diagram.getAttribute("aria-labelledby")!;
  const title = document.getElementById(name)!.textContent!;
  for (const step of STEPS) expect(title).toContain(step);
  expect(title).toContain("joins at the design step");
});

test("a help that cannot be loaded says so and shows no topic", async () => {
  renderHelp({ status: 500, body: { detail: "boom" } });
  expect(await screen.findByRole("alert")).toHaveTextContent("The help could not be loaded.");
  expect(document.querySelector("details")).toBeNull();
});
