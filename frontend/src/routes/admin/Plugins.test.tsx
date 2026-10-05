import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import Plugins from "./Plugins";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.endsWith("/admin/plugins")) {
        return new Response(
          JSON.stringify([
            {
              name: "room_fit",
              description: "room check",
              kind: "builtin",
              role: "designer",
              tools: ["room_fit"],
              enabled: true,
              toggleable: true,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/admin/plugins/room_fit")) {
        return new Response(JSON.stringify({ name: "room_fit", enabled: false }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("nope", { status: 404 });
    }),
  );
});

test("the developer can disable a plugin", async () => {
  const user = userEvent.setup();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Plugins />
    </QueryClientProvider>,
  );
  const box = await screen.findByLabelText("enable room_fit");
  expect(box).toBeChecked();
  await user.click(box);
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("/admin/plugins/room_fit"),
    expect.objectContaining({ method: "PUT" }),
  );
});
