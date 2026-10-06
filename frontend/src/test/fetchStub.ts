import { vi } from "vitest";

export type Reply = { status?: number; body?: unknown };
type Handler = (url: string, init: RequestInit) => Reply | undefined;

/** Replaces `fetch` with `handler`; every call is recorded as `[method, url, parsed body]`. */
export function stubFetch(handler: Handler) {
  const calls: [string, string, unknown][] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo, init: RequestInit = {}) => {
      const url = String(input);
      const method = init.method ?? "GET";
      calls.push([method, url, init.body ? JSON.parse(String(init.body)) : undefined]);
      const reply = handler(`${method} ${url}`, init) ?? { status: 404, body: { detail: "not found" } };
      const status = reply.status ?? 200;
      return new Response(status === 204 ? null : JSON.stringify(reply.body ?? {}), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}
