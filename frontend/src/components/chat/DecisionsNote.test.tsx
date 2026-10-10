import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import { DecisionsNote } from "./DecisionsNote";

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DecisionsNote threadId="t1" />
    </QueryClientProvider>,
  );
}

test("no note yet offers compress now, which shows the written note", async () => {
  stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: null, note: null, owner_edited: false } };
    if (call === "POST /chat/threads/t1/note/compress")
      return { body: { package_id: null, note: "wall: 3 m wide", owner_edited: false } };
  });
  show();
  expect(await screen.findByText("There is no note yet.")).toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole("button", { name: "Compress now" }));
  expect(await screen.findByText("wall: 3 m wide")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/token|model|deepseek|cost/i);
});

test("the owner corrects the note and it is marked as theirs", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: "hall-bench", note: "doors: hinged", owner_edited: false } };
    if (call === "PUT /chat/threads/t1/note")
      return { body: { package_id: "hall-bench", note: "doors: push-latch", owner_edited: true } };
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Correct" }));
  const box = screen.getByLabelText("Your correction");
  await user.clear(box);
  await user.type(box, "doors: push-latch");
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("doors: push-latch")).toBeInTheDocument();
  expect(screen.getByText("Corrected by you.")).toBeInTheDocument();
  expect(calls).toContainEqual(["PUT", "/chat/threads/t1/note", { note: "doors: push-latch" }]);
});

test("a refused compression says why", async () => {
  stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: null, note: null, owner_edited: false } };
    if (call === "POST /chat/threads/t1/note/compress")
      return { status: 409, body: { detail: { failure_class: "not_compressed", reason: "the conversation could not be compressed now; try again later" } } };
  });
  show();
  await userEvent.setup().click(await screen.findByRole("button", { name: "Compress now" }));
  expect(await screen.findByText(/could not be compressed now/)).toBeInTheDocument();
});
