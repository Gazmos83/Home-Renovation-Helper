import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import Conversations from "./Conversations";

const tools = [
  { plugin: "room_fit", description: "Check whether a piece fits a room", enabled: true, toggleable: true },
  { plugin: "create_piece", description: "Create a new piece", enabled: true, toggleable: false },
];

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/chat/threads") && !url.includes("tools") && init?.method !== "PUT") {
        return new Response(JSON.stringify([{ thread_id: "t1", title: "Hall", package_id: null }]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/tools/room_fit")) {
        return new Response(JSON.stringify({ ...tools[0], enabled: false }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/tools")) {
        return new Response(JSON.stringify(tools), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response("nope", { status: 404 });
    }),
  );
});

function ui() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Conversations />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("the owner can switch a toggleable tool off", async () => {
  const user = userEvent.setup();
  ui();
  const checkbox = await screen.findByLabelText("room_fit");
  expect(checkbox).toBeChecked();
  await user.click(checkbox);
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("/chat/threads/t1/tools/room_fit"),
    expect.objectContaining({ method: "PUT" }),
  );
});

test("a non-toggleable tool is shown always on", async () => {
  ui();
  const checkbox = await screen.findByLabelText("create_piece");
  expect(checkbox).toBeChecked();
  expect(checkbox).toBeDisabled();
  expect(screen.getByText("Always on")).toBeInTheDocument();
});
