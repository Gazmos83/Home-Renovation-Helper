import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import Conversations from "./Conversations";

const hall = {
  thread_id: "t1", title: "Hall bench", package_id: "hall-bench",
  created_at: "2026-10-06T08:00:00Z", last_turn_at: "2026-10-06T09:30:00Z",
};
const fresh = { ...hall, thread_id: "t2", title: "Kitchen", package_id: null };

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/conversations"]}>
        <Routes>
          <Route path="/conversations" element={<Conversations />} />
          <Route path="/conversations/:threadId" element={<p>the conversation</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("a conversation shows its title, its piece and when it last had a turn", async () => {
  stubFetch((call) => (call === "GET /chat/threads" ? { body: [hall, fresh] } : undefined));
  show();
  const entry = await screen.findByRole("link", { name: /Hall bench/ });
  expect(entry).toHaveAttribute("href", "/conversations/t1");
  expect(entry).toHaveTextContent("hall-bench");
  expect(entry.querySelector("time")).toHaveAttribute("datetime", hall.last_turn_at);
  expect(screen.getByRole("link", { name: /Kitchen/ })).not.toHaveTextContent("hall-bench");
});

test("clicking a conversation opens it", async () => {
  stubFetch((call) => (call === "GET /chat/threads" ? { body: [hall] } : undefined));
  show();
  await userEvent.setup().click(await screen.findByRole("link", { name: /Hall bench/ }));
  expect(await screen.findByText("the conversation")).toBeInTheDocument();
});

test("starting a conversation sends the title and opens it", async () => {
  const user = userEvent.setup();
  const calls = stubFetch((call) => {
    if (call === "GET /chat/threads") return { body: [] };
    if (call === "POST /chat/threads") return { status: 201, body: { ...fresh, thread_id: "t9" } };
  });
  show();
  const title = await screen.findByLabelText("Conversation title");
  await user.clear(title);
  await user.type(title, "Kitchen");
  await user.click(screen.getByRole("button", { name: "Start" }));
  expect(await screen.findByText("the conversation")).toBeInTheDocument();
  expect(calls).toContainEqual(["POST", "/chat/threads", { title: "Kitchen" }]);
});
