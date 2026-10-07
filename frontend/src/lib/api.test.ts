import { afterEach, expect, test, vi } from "vitest";
import { api, ApiError, sseParser, type TurnEvent } from "./api";

const STREAM =
  'event: specialist\ndata: {"role": "designer"}\n\n' +
  'event: tool\ndata: {"plugin": "revise package"}\n\n' +
  'event: reply\ndata: {"reply": "Two lines\\nof text", "specialists": ["designer"]}\n\n' +
  "event: done\ndata: {}\n\n";

afterEach(() => vi.unstubAllGlobals());

test("chunked text split mid-line gives each event once, in order", () => {
  for (const size of [1, 3, 7, 20, STREAM.length]) {
    const seen: TurnEvent[] = [];
    const parser = sseParser((event) => seen.push(event));
    for (let at = 0; at < STREAM.length; at += size) parser.push(STREAM.slice(at, at + size));
    parser.end();
    expect(seen.map((e) => e.event)).toEqual(["specialist", "tool", "reply", "done"]);
    expect(seen[0].data).toEqual({ role: "designer" });
    expect(seen[2].data).toEqual({ reply: "Two lines\nof text", specialists: ["designer"] });
  }
});

test("CRLF line endings and a last event without its blank line are read", () => {
  const seen: TurnEvent[] = [];
  const parser = sseParser((event) => seen.push(event));
  parser.push('event: title\r\ndata: {"title": "Hall bench"}\r\n\r\nevent: done\r\ndata: {}');
  parser.end();
  expect(seen).toEqual([
    { event: "title", data: { title: "Hall bench" } },
    { event: "done", data: {} },
  ]);
});

test("a streamed turn reads the response body as it arrives", async () => {
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(STREAM.slice(0, 30)));
      controller.enqueue(encoder.encode(STREAM.slice(30)));
      controller.close();
    },
  });
  const fetchMock = vi.fn(async () => new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } }));
  vi.stubGlobal("fetch", fetchMock);
  const seen: string[] = [];
  await api.streamTurn("t1", "one more shelf", [], (event) => seen.push(event.event));
  expect(seen).toEqual(["specialist", "tool", "reply", "done"]);
  expect(fetchMock).toHaveBeenCalledWith(
    "/chat/threads/t1/turns/stream",
    expect.objectContaining({ method: "POST", body: JSON.stringify({ message: "one more shelf", upload_ids: [] }) }),
  );
});

test("a refusal before the stream opens is thrown in the service's words", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(JSON.stringify({ detail: { failure_class: "confirmation_pending", reason: "answer the pending questions first" } }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  const error = await api.streamTurn("t1", "hello", [], () => undefined).catch((e: unknown) => e);
  expect(error).toBeInstanceOf(ApiError);
  expect((error as ApiError).status).toBe(409);
  expect((error as ApiError).message).toBe("answer the pending questions first");
});
