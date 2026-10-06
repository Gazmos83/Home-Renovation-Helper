import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import GuidelineNotes from "./GuidelineNotes";

const note = { id: "n1", title: "Wardrobe passage", body: "Keep it clear.", value: 900, unit: "mm", citation: "Neufert p. 123" };

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><GuidelineNotes /></QueryClientProvider>);
}

test("a note shows its citation, can be edited and deleted", async () => {
  const user = userEvent.setup();
  const calls = stubFetch((call) => {
    if (call === "GET /guideline-notes") return { body: [note] };
    if (call === "PUT /guideline-notes/n1") return { body: note };
    if (call === "DELETE /guideline-notes/n1") return { status: 204 };
  });
  show();
  expect(await screen.findByText("Source: Neufert p. 123")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Edit Wardrobe passage" }));
  await user.click(screen.getByRole("button", { name: "Save note" }));
  await user.click(await screen.findByRole("button", { name: "Delete Wardrobe passage" }));
  expect(calls.find(([m]) => m === "PUT")![2]).toMatchObject({ citation: "Neufert p. 123", value: 900, unit: "mm" });
  expect(calls.some(([m, u]) => m === "DELETE" && u === "/guideline-notes/n1")).toBe(true);
});

test("a note without a citation is refused next to the citation field", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /guideline-notes") return { body: [] };
    if (call === "POST /guideline-notes") {
      return { status: 422, body: { detail: { failure_class: "refused", reason: "a note needs a source citation", field: "citation" } } };
    }
  });
  show();
  await user.type(await screen.findByLabelText("Title"), "A rule");
  await user.type(screen.getByLabelText("Text"), "Something");
  await user.click(screen.getByRole("button", { name: "Add note" }));
  const message = await screen.findByText("a note needs a source citation");
  expect(message.previousElementSibling).toBe(screen.getByLabelText("Source citation"));
});
