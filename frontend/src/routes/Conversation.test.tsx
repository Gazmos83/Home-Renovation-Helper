import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { setWorkspaceLayout } from "../lib/workspaceLayout";
import Workspace from "./Workspace";
import type { Brief } from "../lib/api";

// No WebGL in jsdom: the 3D stage is a stub.
vi.mock("@/components/inspector/InspectorCanvas", () => ({ default: () => <div data-testid="canvas" /> }));

const SPEC = {
  name: "Hall bench", units: "mm", overall: { w: 1200, h: 450, d: 400 }, modules: {},
  layers: { carcass: ["side"] }, parts: [], hardware: [],
};

type Msg = {
  role: "owner" | "assistant" | "confirmation" | "notice";
  text: string;
  message_id?: string;
  outcome?: "succeeded" | "failed";
  tier?: string;
  package_id?: string;
  version?: number;
  upload_ids?: string[];
  kind?: "text" | "answers" | "render" | "build" | "revision";
  rows?: { question: string; answer: string }[];
  title?: string;
  summary?: string;
  answer?: "yes" | "no";
  reason?: string;
  table?: { columns: string[]; rows: string[][] };
};
type Reply = { status?: number; body?: unknown };
type Event = { event: string; data: unknown };
/** A streamed route's answer: a refusal before the stream opens, or its events. */
type Streamed = Reply | { events: Event[] | ReadableStream<Uint8Array> };

const STEPS = ["brief", "piece", "built", "rendered", "reviewed", "detail", "final"];
function progress(done: string[], extra: Record<string, unknown> = {}) {
  return {
    package_id: "hall-bench", name: "Hall bench", latest_version: 1, approved_version: null, build_status: "succeeded",
    version_count: 1, max_versions: 15,
    steps: STEPS.map((step) => ({ step, done: done.includes(step), detail: null })),
    next_step: "Ask for a draft render", open_review_items: 0, open_requests: [],
    screenshot: null, still: null, viewer: null, rendering: false, ...extra,
  };
}

let messages: Msg[];
let title: string;
let pending: unknown;
let progressNow: unknown;
let turn: (body: Record<string, unknown>) => Promise<Streamed> | Streamed;
let resume: (body: Record<string, unknown>) => Promise<Streamed> | Streamed;
let upload: () => Reply;
let calls: [string, string, unknown][];
/** Answers a test adds before the shared ones; `undefined` falls through to them. */
let extra: (call: string) => Reply | undefined;

const json = (reply: Reply) =>
  new Response(JSON.stringify(reply.body ?? {}), { status: reply.status ?? 200, headers: { "Content-Type": "application/json" } });

const sseText = (events: Event[]) => events.map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`).join("");

function streamed(reply: Streamed): Response {
  if (!("events" in reply)) return json(reply);
  const body = Array.isArray(reply.events) ? sseText(reply.events) : reply.events;
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

/** The events of a turn that ends with `reply`. */
const replied = (text: string, ...roles: string[]): Event[] => [
  ...roles.map((role) => ({ event: "specialist", data: { role } })),
  { event: "reply", data: { reply: text, specialists: roles } },
  { event: "done", data: {} },
];

/** A stream whose events the test sends one at a time. */
function controlledStream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const stream = new ReadableStream<Uint8Array>({ start: (c) => void (controller = c) });
  const encoder = new TextEncoder();
  return {
    stream,
    send: (event: Event) => controller.enqueue(encoder.encode(sseText([event]))),
    close: () => controller.close(),
  };
}

beforeEach(() => {
  messages = [];
  title = "Hall bench";
  pending = null;
  progressNow = progress([]);
  briefNow = {
    confirmed: true, room: "Hall", purpose: "a bench by the door", max_piece_height_mm: 900,
    max_piece_height_from_version: null, style: "oak", budget_eur: 400, rooms: ["Hall", "Kitchen"],
  };
  calls = [];
  extra = () => undefined;
  turn = () => ({ events: replied("ok", "intake") });
  resume = () => ({ events: replied("ok", "designer") });
  upload = () => ({ status: 201, body: { upload_id: "u1", kind: "jpeg", size_bytes: 3, original_name: "blueprint.jpeg" } });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo, init: RequestInit = {}) => {
      const url = String(input);
      const method = init.method ?? "GET";
      const body = typeof init.body === "string" ? JSON.parse(init.body) : init.body;
      calls.push([method, url, body]);
      const call = `${method} ${url}`;
      const added = extra(call);
      if (added) return json(added);
      const roomApproval = /^(PUT|DELETE) \/compositions\/([^/]+)\/versions\/(\d+)\/approval$/.exec(call);
      if (roomApproval) {
        const version = Number(roomApproval[3]);
        const current = progressNow as {
          room?: { approved_version?: number | null; versions?: { version: number; approved_at?: string | null }[] };
        };
        if (current.room) {
          const approved = roomApproval[1] === "PUT" ? version : null;
          progressNow = {
            ...current,
            room: {
              ...current.room,
              approved_version: approved,
              versions: (current.room.versions ?? []).map((v) => ({
                ...v,
                approved_at: v.version === approved ? "2026-10-10T00:00:00Z" : null,
              })),
            },
          };
        }
        return json({
          body: {
            slug: roomApproval[2],
            version,
            status: "succeeded",
            approved_at: roomApproval[1] === "PUT" ? "2026-10-10T00:00:00Z" : null,
          },
        });
      }
      if (call === "GET /chat/threads/t1")
        return json({ body: { thread_id: "t1", title, package_id: null, created_at: "", last_turn_at: "", messages, pending } });
      if (call === "GET /chat/threads/t1/progress") return json({ body: progressNow });
      if (call === "GET /chat/threads/t1/brief") return json({ body: briefNow });
      if (call === "PUT /chat/threads/t1/brief") {
        briefNow = { ...briefNow, confirmed: true, ...body, rooms: briefNow.rooms };
        return json({ body: briefNow });
      }
      if (call === "GET /packages/hall-bench/versions/1")
        return json({ body: { package_id: "hall-bench", version: 1, status: "succeeded", approved_at: null, files: ["model.glb", "spec.json"] } });
      if (call === "GET /packages/hall-bench/versions/1/files/spec.json") return json({ body: SPEC });
      if (call === "GET /packages/hall-bench/versions/2")
        return json({ body: { package_id: "hall-bench", version: 2, status: "queued", approved_at: null, files: [] } });
      if (call === "GET /packages/hall-bench/versions/4")
        return json({ body: { package_id: "hall-bench", version: 4, status: "succeeded", approved_at: null, files: ["model.glb", "spec.json"] } });
      if (call === "GET /packages/hall-bench/versions/4/files/spec.json") return json({ body: SPEC });
      const rendersOf = /^GET \/packages\/hall-bench\/versions\/(\d)\/renders$/.exec(call);
      if (rendersOf) {
        const base = `/packages/hall-bench/versions/${rendersOf[1]}/files`;
        return json({
          body: [
            { render: "turntable", label: "Turntable", tier: "draft", finished_at: "2026-10-15T09:00:00+00:00", frames: 12,
              preview: `${base}/frames/0`, viewer: null, can_rate: true, rating: null, comment: null },
            { render: "detail-still", label: "Detailed still", tier: "final", finished_at: "2026-10-15T10:00:00+00:00", frames: 0,
              preview: `${base}/detail/still.png`, viewer: null, can_rate: true, rating: null, comment: null },
            { render: "detail-turntable", label: "Detailed turntable", tier: "final", finished_at: "2026-10-15T12:00:00+00:00", frames: 36,
              preview: `${base}/detail/frames/0`, viewer: null, can_rate: true, rating: null, comment: null },
            { render: "still", label: "Still", tier: "draft", finished_at: "2026-10-15T13:00:00+00:00", frames: 0,
              preview: `${base}/still.png`, viewer: null, can_rate: true, rating: null, comment: null },
          ],
        });
      }
      if (call === "GET /chat/threads/t1/uploads")
        return json({ body: [{ upload_id: "u1", kind: "jpeg", size_bytes: 3, original_name: "blueprint.jpeg" }] });
      const approval = /^(PUT|DELETE) \/packages\/hall-bench\/versions\/(\d)\/approval$/.exec(call);
      if (approval) {
        const version = Number(approval[2]);
        progressNow = { ...(progressNow as object), approved_version: approval[1] === "PUT" ? version : null };
        return json({ body: { package_id: "hall-bench", version, status: "succeeded", approved_at: null } });
      }
      if (call === "POST /chat/threads/t1/turns/stream") return streamed(await turn(body));
      if (call === "POST /chat/threads/t1/turns/latest") return streamed(await turn(body));
      if (call === "POST /chat/threads/t1/resume/stream") return streamed(await resume(body));
      if (call === "PATCH /chat/threads/t1") {
        title = String(body.title);
        return json({ body: { thread_id: "t1", title, package_id: null, created_at: "", last_turn_at: "" } });
      }
      if (call === "DELETE /chat/threads/t1") {
        return new Response(null, { status: 204 });
      }
      if (call === "POST /chat/threads/t1/uploads") return json(upload());
      return json({ status: 404, body: { detail: "not found" } });
    }),
  );
});

afterEach(() => vi.useRealTimers());

let briefNow: Brief;

async function openPanel(name: string) {
  await userEvent.setup().click(await screen.findByRole("button", { name }));
  return screen.findByRole("region", { name });
}
const openProject = () => openPanel("Project");
const openBrief = async () => {
  await userEvent.setup().click(await screen.findByRole("button", { name: "Brief" }));
  return screen.findByRole("form", { name: "Brief" });
};

/** The Workspace tab's body, as the Design Studio renders it for `/studio/workspace/<id>`. */
function Conversation() {
  return <Workspace threadId={useParams().threadId} />;
}

function show(path = "/studio/workspace/t1") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/studio/workspace/:threadId" element={<Conversation />} />
          <Route path="/pieces" element={<p>the pieces page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const card = { confirmation_id: "c1", subject: "revise", title: "Revising piece", summary: "cabinet: 2 shelves → 3", proposal: {} };
const owner = (text: string) => ({ role: "owner" as const, text });
const reply = (text: string) => ({ role: "assistant" as const, text });

test("the history is shown in order", async () => {
  messages = [owner("a hall bench"), reply("How wide?")];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  expect(list.getByText("a hall bench")).toBeInTheDocument();
  expect(list.getByText("How wide?")).toBeInTheDocument();
});

test("with no piece yet the piece pane says so and no 3D stage is loaded (No piece yet)", async () => {
  progressNow = progress([], { package_id: null, name: null, latest_version: null, build_status: null, version_count: 0 });
  messages = [owner("a hall bench"), reply("How wide?")];
  show();
  await screen.findByText("How wide?");
  expect(await screen.findByText("No piece has been designed yet in this conversation.")).toBeInTheDocument();
  expect(screen.queryByTestId("canvas")).not.toBeInTheDocument();
  expect(screen.queryByRole("complementary", { name: "Inspector" })).not.toBeInTheDocument();
});

test("the piece pane shows the conversation's piece at its latest version by default (Bound piece by default)", async () => {
  messages = [reply("Hello")];
  show();
  const inspector = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await inspector.findByText("Overall: W 1200 mm × H 450 mm × D 400 mm")).toBeInTheDocument();
  expect(calls.map(([, url]) => url)).toContain("/packages/hall-bench/versions/1");
});

test("sending shows the message on the right, a waiting bubble naming the Foreman then Intake, then the reply", async () => {
  const user = userEvent.setup();
  const live = controlledStream();
  turn = () => ({ events: live.stream });
  show();
  await user.type(await screen.findByLabelText("Message"), "I want a bench for the hall");
  await user.click(screen.getByRole("button", { name: "Send" }));

  const list = within(screen.getByRole("region", { name: "Messages" }));
  const sent = list.getByText("I want a bench for the hall");
  expect(sent.closest("[data-side]")).toHaveAttribute("data-side", "right");
  expect(screen.getByLabelText("Message")).toBeDisabled();
  const waiting = await screen.findByRole("status");
  expect(waiting).toHaveTextContent("The Foreman is working…");
  expect(waiting.closest("[data-side]")).toHaveAttribute("data-side", "left");
  expect(waiting.className).toContain("border-2");

  live.send({ event: "specialist", data: { role: "intake" } });
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Intake is working…"));

  messages = [owner("I want a bench for the hall"), reply("How wide is the hall?")];
  live.send({ event: "reply", data: { reply: "How wide is the hall?", specialists: ["intake"] } });
  live.send({ event: "done", data: {} });
  live.close();

  const answer = await list.findByText("How wide is the hall?");
  expect(answer.closest("[data-side]")).toHaveAttribute("data-side", "left");
  expect(within(list.getByLabelText("Specialists in this turn")).getByText("Intake")).toBeInTheDocument();
  expect(list.getAllByText("I want a bench for the hall")).toHaveLength(1);
  await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  await waitFor(() => expect(screen.getByLabelText("Message")).toBeEnabled());
  expect(calls).toContainEqual(["POST", "/chat/threads/t1/turns/stream", { message: "I want a bench for the hall", upload_ids: [] }]);
});

test("a refused turn shows its reason, keeps no message and gives the words back", async () => {
  const user = userEvent.setup();
  turn = () => ({ status: 503, body: { detail: { failure_class: "unavailable", reason: "the conversation memory is not available right now" } } });
  show();
  await user.type(await screen.findByLabelText("Message"), "a bench");
  await user.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("the conversation memory is not available right now");
  const list = within(screen.getByRole("region", { name: "Messages" }));
  expect(list.queryByText("a bench")).not.toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Message")).toHaveValue("a bench");
});

test("a 409 while a confirmation is pending shows the confirmation", async () => {
  const user = userEvent.setup();
  turn = () => {
    pending = card;
    return { status: 409, body: { detail: { failure_class: "confirmation_pending", reason: "answer the pending revise confirmation first" } } };
  };
  show();
  await user.type(await screen.findByLabelText("Message"), "and a shelf");
  await user.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByRole("region", { name: "Confirmation needed" })).toBeInTheDocument();
  expect(screen.queryByLabelText("Message")).not.toBeInTheDocument();
});

test("a conversation reopened with a confirmation pending shows the card and hides the composer", async () => {
  pending = card;
  show();
  const shown = within(await screen.findByRole("region", { name: "Confirmation needed" }));
  expect(shown.getByText(/cabinet: 2 shelves/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Message")).not.toBeInTheDocument();
});

test("Yes sends the answer, shows the reply that follows and brings the composer back", async () => {
  const user = userEvent.setup();
  pending = card;
  resume = () => {
    pending = null;
    messages = [reply("Version 2 is created.")];
    return { events: replied("Version 2 is created.", "designer") };
  };
  show();
  await user.click(await screen.findByRole("button", { name: "Yes" }));
  expect(await screen.findByText("Version 2 is created.")).toBeInTheDocument();
  expect(await screen.findByLabelText("Message")).toBeInTheDocument();
  expect(calls).toContainEqual(["POST", "/chat/threads/t1/resume/stream", { confirmation_id: "c1", answer: "yes" }]);
});

test("No sends the reason with the answer", async () => {
  const user = userEvent.setup();
  pending = card;
  resume = () => {
    pending = null;
    messages = [reply("Shall I make it 4 shelves?")];
    return { events: replied("Shall I make it 4 shelves?", "designer") };
  };
  show();
  await user.type(await screen.findByLabelText("Reason (optional)"), "make it 4 shelves");
  await user.click(screen.getByRole("button", { name: "No" }));
  expect(await screen.findByText("Shall I make it 4 shelves?")).toBeInTheDocument();
  expect(calls).toContainEqual(["POST", "/chat/threads/t1/resume/stream", { confirmation_id: "c1", answer: "no", reason: "make it 4 shelves" }]);
});

test("an attached plan is shown as a thumbnail and sent with the turn", async () => {
  const user = userEvent.setup();
  show();
  await user.upload(await screen.findByLabelText("Add a plan, photo, design or note"), new File(["x"], "blueprint.jpeg", { type: "image/jpeg" }));
  expect(await screen.findByRole("img", { name: "blueprint.jpeg" })).toHaveAttribute("src", "/uploads/u1");
  await user.type(screen.getByLabelText("Message"), "This is my flat");
  await user.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(calls).toContainEqual(["POST", "/chat/threads/t1/turns/stream", { message: "This is my flat", upload_ids: ["u1"] }]),
  );
});

test("a sent plan keeps its thumbnail in the history after the reply", async () => {
  messages = [{ role: "owner", text: "This is my flat", upload_ids: ["u1"] }, reply("I can see the plan.")];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  expect(await list.findByRole("img", { name: "blueprint.jpeg" })).toHaveAttribute("src", "/uploads/u1");
});

test("the uploads are not read when no message carried a file", async () => {
  messages = [owner("a hall bench"), reply("How wide?")];
  show();
  await screen.findByText("How wide?");
  expect(calls.some(([, url]) => url === "/chat/threads/t1/uploads")).toBe(false);
});

test("a refused upload shows the service's reason and attaches nothing", async () => {
  const user = userEvent.setup();
  upload = () => ({ status: 413, body: { detail: { failure_class: "too_large", reason: "the image is too large" } } });
  show();
  await user.upload(await screen.findByLabelText("Add a plan, photo, design or note"), new File(["x"], "huge.jpeg", { type: "image/jpeg" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("the image is too large");
  expect(screen.queryByRole("img", { name: "huge.jpeg" })).not.toBeInTheDocument();
});

test("the piece pane shows the shown version's build state, and a building version offers no control (Unbuilt version offers no control)", async () => {
  show("/studio/workspace/t1?inspect=hall-bench/2");
  const pane = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await pane.findByText("queued")).toBeInTheDocument();
  expect(pane.queryByRole("button", { name: /approve version 2/i })).not.toBeInTheDocument();
  expect(pane.queryByRole("button", { name: "Delete version 2" })).not.toBeInTheDocument();
});
test("the Project panel shows the progress steps and the next step, and nothing of the piece or room", async () => {
  progressNow = progress(["brief", "piece", "built"], { room: HALL, next_step: "Ask for a draft render" });
  show();
  const panel = within(await openProject());
  expect(await panel.findByText(/Ask for a draft render/)).toBeInTheDocument();
  expect(panel.getByText("Built").closest("li")).toHaveAttribute("data-done", "true");
  expect(panel.queryByRole("group", { name: "Approval" })).not.toBeInTheDocument();
  expect(panel.queryByRole("group", { name: "Room" })).not.toBeInTheDocument();
  expect(panel.queryByRole("button", { name: /Inspect/ })).not.toBeInTheDocument();
});

test("open review items are counted and link to the piece's page", async () => {
  progressNow = progress(["brief", "piece", "built", "rendered", "reviewed"], { open_review_items: 2 });
  show();
  const panel = within(await openProject());
  expect(await panel.findByText(/2 open review items/)).toBeInTheDocument();
  expect(panel.getByRole("link", { name: "Open the piece's page" })).toHaveAttribute("href", "/pieces");
});

test("the Piece icon opens the inspector at the latest version, switching the layout, with no flyout (Piece icon opens the inspector)", async () => {
  const user = userEvent.setup();
  setWorkspaceLayout("chat-room");
  progressNow = progress(["brief", "piece", "built"], { room: HALL });
  serveRoom();
  show();
  await screen.findByRole("complementary", { name: "Room view" });
  await user.click(await screen.findByRole("button", { name: "Piece" }));
  const inspector = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await inspector.findByRole("group", { name: "Approval of the shown version" })).toBeInTheDocument();
  expect(await inspector.findByText("Overall: W 1200 mm × H 450 mm × D 400 mm")).toBeInTheDocument();
  expect(window.localStorage.getItem("studio.workspace.layout")).toBe("chat-piece");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.queryByRole("complementary", { name: "Room view" })).not.toBeInTheDocument();
});

test("the Piece icon closes an open flyout and opens none (Piece icon opens no flyout)", async () => {
  const user = userEvent.setup();
  show();
  await openBrief();
  await user.click(screen.getByRole("button", { name: "Piece" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(await screen.findByRole("complementary", { name: "Inspector" })).toBeInTheDocument();
  expect(calls.some(([m]) => m === "POST")).toBe(false);
});

test("with no piece the Piece icon shows the piece pane, which says so (No piece yet)", async () => {
  const user = userEvent.setup();
  setWorkspaceLayout("chat-room");
  progressNow = { ...progress([]), package_id: null, name: null, latest_version: null, build_status: null, version_count: 0 };
  show();
  await user.click(await screen.findByRole("button", { name: "Piece" }));
  expect(await screen.findByText("No piece has been designed yet in this conversation.")).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
test("a render route in a reply is a link without its full stop; other addresses stay text", async () => {
  messages = [
    owner("render it"),
    reply("Started a draft turntable of hall-bench version 1. When it finishes it will be at /packages/hall-bench/versions/1/files/viewer.html."),
    reply("See https://example.com/packages/x/versions/1/files/viewer.html or /admin/models."),
  ];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  const link = await list.findByRole("link", { name: "/packages/hall-bench/versions/1/files/viewer.html" });
  expect(link).toHaveAttribute("href", "/packages/hall-bench/versions/1/files/viewer.html");
  expect(link).toHaveAttribute("target", "_blank");
  expect(list.getAllByRole("link")).toHaveLength(1);
  expect(list.getByText(/https:\/\/example\.com/)).toBeInTheDocument();
});

test("a route the reply puts in backticks is linked without them", async () => {
  messages = [reply("The viewer will be here: `/packages/hall-bench/versions/1/files/viewer.html` once done.")];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  const link = await list.findByRole("link");
  expect(link).toHaveAttribute("href", "/packages/hall-bench/versions/1/files/viewer.html");
});

test("a route the owner typed stays text", async () => {
  messages = [owner("what is at /packages/hall-bench/versions/1/files/viewer.html")];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  await list.findByText(/what is at/);
  expect(list.queryByRole("link")).not.toBeInTheDocument();
});

test("an attached design file shows as a named chip, not a thumbnail, and is sent with the turn", async () => {
  const user = userEvent.setup();
  upload = () => ({ status: 201, body: { upload_id: "d1", kind: "design", size_bytes: 900, original_name: "wall-unit.json" } });
  show();
  await user.upload(
    await screen.findByLabelText("Add a plan, photo, design or note"),
    new File(['{"kind":"custom_build"}'], "wall-unit.json", { type: "application/json" }),
  );
  expect(await screen.findByLabelText("Design file wall-unit.json")).toHaveTextContent("wall-unit.json");
  expect(screen.queryByRole("img", { name: "wall-unit.json" })).not.toBeInTheDocument();
  await user.type(screen.getByLabelText("Message"), "Import this");
  await user.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(calls).toContainEqual(["POST", "/chat/threads/t1/turns/stream", { message: "Import this", upload_ids: ["d1"] }]),
  );
});

test("a file that is not a design is refused in plain words", async () => {
  const user = userEvent.setup();
  upload = () => ({
    status: 415,
    body: { detail: { failure_class: "unsupported_type", reason: "only PNG and JPEG images and design files (.json) are accepted" } },
  });
  show();
  await user.upload(
    await screen.findByLabelText("Add a plan, photo, design or note"),
    new File(["[]"], "list.json", { type: "application/json" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("design files (.json) are accepted");
  expect(screen.queryByLabelText("Design file list.json")).not.toBeInTheDocument();
});

const ROOM_TABLE = {
  columns: ["Item", "Kind", "Size (mm)", "Placement", "Centre (mm)", "Rotation"],
  rows: [
    ["Sofa", "stand-in", "2200 × 950 × 800", "wall 2, 400 mm", "1500, 475", "0°"],
    ["Lamp", "model", "400 × 400 × 1600", "free, 0°", "1800, 2100", "0°"],
  ],
};
const roomAnswered = {
  role: "confirmation" as const,
  text: "compose_room: Room Wohnen: 2 item(s) — yes",
  title: "Composing room", summary: "Room Wohnen: 2 item(s)\nCompared with version 2: moved: sofa", answer: "yes" as const,
  table: ROOM_TABLE,
};

test("an answered room change is collapsed to its title and answer, and its dropdown shows the calculations (Room change collapsed, Calculations opened)", async () => {
  const user = userEvent.setup();
  messages = [owner("compose Wohnen"), roomAnswered, reply("Created Wohnen version 3.")];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  const row = (await list.findByText("Composing room · Yes")).closest("[data-role=confirmation]") as HTMLElement;
  expect(within(row).queryByRole("table")).not.toBeInTheDocument();
  expect(list.queryByText(/compose_room/)).not.toBeInTheDocument();
  const toggle = within(row).getByRole("button", { name: "Show details of Composing room" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  await user.click(toggle);
  const table = within(row).getByRole("table", { name: "Calculations" });
  expect(within(table).getAllByRole("row")).toHaveLength(3);
  expect(within(table).getByText("wall 2, 400 mm")).toBeInTheDocument();
  expect(within(row).getByText(/Compared with version 2: moved: sofa/)).toBeInTheDocument();
  await user.click(toggle);
  expect(within(row).queryByRole("table")).not.toBeInTheDocument();
  expect(calls.some(([m]) => m === "POST")).toBe(false);
});

test("a declined revision reads its title, No and the reason, and its dropdown has no table (Declined revision with a reason)", async () => {
  const user = userEvent.setup();
  messages = [
    owner("a hall bench"),
    { role: "confirmation", text: "revise: cabinet: 2 shelves → 3 — no (make it 4 shelves)", title: "Revising piece",
      summary: "cabinet: 2 shelves → 3", answer: "no", reason: "make it 4 shelves" },
    reply("Four shelves, then?"),
  ];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  const row = (await list.findByText("Revising piece · No — make it 4 shelves")).closest("[data-role=confirmation]") as HTMLElement;
  await user.click(within(row).getByRole("button", { name: "Show details of Revising piece" }));
  expect(within(row).getByText("cabinet: 2 shelves → 3")).toBeInTheDocument();
  expect(within(row).queryByRole("table")).not.toBeInTheDocument();
});

test("every answered confirmation starts collapsed again after a reload (Collapsed after a reload)", async () => {
  const user = userEvent.setup();
  messages = [owner("compose Wohnen"), roomAnswered];
  show();
  await user.click(await screen.findByRole("button", { name: "Show details of Composing room" }));
  expect(screen.getByRole("table", { name: "Calculations" })).toBeInTheDocument();
  cleanup();
  show();
  expect(await screen.findByRole("button", { name: "Show details of Composing room" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("table", { name: "Calculations" })).not.toBeInTheDocument();
});

test("a pending room change is headed with its plain title and shows its table (Plain heading for a room change)", async () => {
  pending = {
    confirmation_id: "c2", subject: "compose_room", title: "Composing room",
    summary: "Room Wohnen: 2 item(s)", proposal: {}, table: ROOM_TABLE,
  };
  show();
  const confirm = within(await screen.findByRole("region", { name: "Confirmation needed" }));
  expect(confirm.getByRole("heading", { name: "Confirm: Composing room" })).toBeInTheDocument();
  expect(within(confirm.getByRole("table", { name: "Calculations" })).getAllByRole("row")).toHaveLength(3);
  expect(screen.queryByText(/compose_room/)).not.toBeInTheDocument();
});

// --- studio-chat-polish -------------------------------------------------------------

test("a Markdown table in a reply is a table with a header row", async () => {
  messages = [
    reply(
      "Cut list:\n\n| Part | Qty | Size |\n|---|---|---|\n| Side | 2 | 430 × 300 |\n| Top | 1 | 1200 × 300 |\n" +
        "| Shelf | 2 | 1160 × 280 |\n| Back | 1 | 1200 × 430 |\n| Plinth | 1 | 1200 × 100 |",
    ),
  ];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  const table = await list.findByRole("table");
  expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Part", "Qty", "Size"]);
  expect(within(table).getAllByRole("row")).toHaveLength(6);
  expect(list.queryByText(/\|/)).not.toBeInTheDocument();
});

test("a calc block is a framed box between the paragraphs around it", async () => {
  messages = [reply("The height adds up:\n\n```calc\n430 + 430 + 400 + 100 + 100 = 1460\n```\n\nThat fits under the window.")];
  show();
  await userEvent.setup().click(await screen.findByRole("button", { name: "Show the maths" }));
  const box = await screen.findByRole("figure", { name: "Calculation" });
  expect(box).toHaveTextContent("430 + 430 + 400 + 100 + 100 = 1460");
  expect(box.className).toContain("border-2");
  const before = screen.getByText("The height adds up:");
  const after = screen.getByText("That fits under the window.");
  expect(before.compareDocumentPosition(box) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(box.compareDocumentPosition(after) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test("HTML in a reply is shown literally and creates no element", async () => {
  messages = [reply("Look: <img src=x onerror=alert(1)> and <b>bold</b>")];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  expect(await list.findByText(/<img src=x onerror=alert\(1\)>/)).toBeInTheDocument();
  expect(list.queryByRole("img")).not.toBeInTheDocument();
  expect(document.querySelector("b")).toBeNull();
});

test("an image in a reply is shown only from the app's own routes", async () => {
  messages = [reply("![the still](/packages/hall-bench/versions/1/files/still.png) and ![tracker](https://example.com/x.png)")];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  expect(await list.findByRole("img", { name: "the still" })).toHaveAttribute("src", "/packages/hall-bench/versions/1/files/still.png");
  expect(list.queryByRole("img", { name: "tracker" })).not.toBeInTheDocument();
  expect(list.getByText("tracker")).toBeInTheDocument();
});

test("an attachment removed before sending is not sent and not shown", async () => {
  const user = userEvent.setup();
  const replies = [
    { status: 201, body: { upload_id: "u1", kind: "jpeg", size_bytes: 3, original_name: "blueprint.jpeg" } },
    { status: 201, body: { upload_id: "n1", kind: "text", size_bytes: 40, original_name: "notes.md" } },
  ];
  upload = () => replies.shift() ?? { status: 500 };
  const live = controlledStream();
  turn = () => ({ events: live.stream });
  show();
  const input = await screen.findByLabelText("Add a plan, photo, design or note");
  await user.upload(input, new File(["x"], "blueprint.jpeg", { type: "image/jpeg" }));
  await user.upload(input, new File(["# notes"], "notes.md", { type: "text/markdown" }));
  expect(await screen.findByLabelText("Note notes.md")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Remove blueprint.jpeg" }));
  expect(screen.queryByRole("img", { name: "blueprint.jpeg" })).not.toBeInTheDocument();

  await user.type(screen.getByLabelText("Message"), "measurements attached");
  await user.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(calls).toContainEqual(["POST", "/chat/threads/t1/turns/stream", { message: "measurements attached", upload_ids: ["n1"] }]),
  );
  const list = within(screen.getByRole("region", { name: "Messages" }));
  expect(list.getByLabelText("Note notes.md")).toBeInTheDocument();
  expect(list.queryByRole("img", { name: "blueprint.jpeg" })).not.toBeInTheDocument();
  live.close();
});

const questions = {
  confirmation_id: "q1",
  kind: "questions",
  subject: "",
  summary: "",
  proposal: {},
  questions: [
    { text: "Ceiling height?", unit: "mm", choices: [] },
    { text: "Budget?", unit: "EUR", choices: [] },
  ],
};

test("two questions are asked one at a time and the answers become a Question | Answer table", async () => {
  const user = userEvent.setup();
  pending = questions;
  resume = () => {
    pending = null;
    messages = [
      owner("a hall bench"),
      { role: "assistant", text: "", kind: "answers", rows: [{ question: "Ceiling height?", answer: "2500 mm" }, { question: "Budget?", answer: "900 EUR" }] },
      reply("Thanks, noted."),
    ];
    return { events: replied("Thanks, noted.", "intake") };
  };
  show();
  const form = within(await screen.findByRole("region", { name: "Questions" }));
  expect(screen.queryByLabelText("Message")).not.toBeInTheDocument();
  expect(form.getByLabelText("Ceiling height?")).toBeInTheDocument();
  expect(form.queryByLabelText("Budget?")).not.toBeInTheDocument();
  expect(form.getByText("mm")).toBeInTheDocument();
  expect(form.getByRole("button", { name: "Next" })).toBeDisabled();

  await user.type(form.getByLabelText("Ceiling height?"), "2500");
  await user.click(form.getByRole("button", { name: "Next" }));
  expect(form.getByLabelText("Budget?")).toBeInTheDocument();
  await user.click(form.getByRole("button", { name: "Back" }));
  expect(form.getByLabelText("Ceiling height?")).toHaveValue("2500");
  await user.click(form.getByRole("button", { name: "Next" }));
  await user.type(form.getByLabelText("Budget?"), "900");
  await user.click(form.getByRole("button", { name: "Send answers" }));

  expect(calls).toContainEqual(["POST", "/chat/threads/t1/resume/stream", { confirmation_id: "q1", answers: ["2500", "900"] }]);
  const table = await within(screen.getByRole("region", { name: "Messages" })).findByRole("table");
  expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Question", "Answer"]);
  expect(within(table).getByText("2500 mm")).toBeInTheDocument();
  expect(within(table).getByText("900 EUR")).toBeInTheDocument();
  expect(await screen.findByLabelText("Message")).toBeInTheDocument();
});

// --- the placement questions (view-piece-in-room) -----------------------------------------

test("the placement question's Room layout button shows the room and keeps the question", async () => {
  const user = userEvent.setup();
  setWorkspaceLayout("chat-piece");
  progressNow = progress(["brief", "piece", "built"], { room: HALL });
  serveRoom();
  pending = {
    ...questions,
    layout: "room",
    questions: [
      { text: "Where would you like to place the piece? Check out the Room layout.", unit: null, choices: ["Wall 1 (3000 mm)", "Wall 2 (2000 mm)"] },
      { text: "How far from the left end of that wall should the piece start? (seen facing the wall)", unit: "mm", choices: [] },
    ],
  };
  show();
  const form = within(await screen.findByRole("region", { name: "Questions" }));
  const sent = calls.length;
  await user.click(form.getByRole("button", { name: "Room layout" }));
  expect(await screen.findByRole("complementary", { name: "Room view" })).toBeInTheDocument();
  expect(window.localStorage.getItem("studio.workspace.layout")).toBe("chat-room");
  expect(screen.getByRole("region", { name: "Questions" })).toBeInTheDocument();
  expect(calls.slice(sent).some(([method]) => method === "POST")).toBe(false);
});

test("other question sets show no Room layout button", async () => {
  pending = questions;
  show();
  const form = within(await screen.findByRole("region", { name: "Questions" }));
  expect(form.queryByRole("button", { name: "Room layout" })).not.toBeInTheDocument();
});

test("a question's choices are buttons and choosing one answers it", async () => {
  const user = userEvent.setup();
  pending = { ...questions, questions: [{ text: "Which wood?", unit: null, choices: ["oak", "birch"] }] };
  show();
  const choices = within(await screen.findByRole("group", { name: "Choices" }));
  expect(choices.getByRole("button", { name: "oak" })).toBeInTheDocument();
  await user.click(choices.getByRole("button", { name: "birch" }));
  await waitFor(() =>
    expect(calls).toContainEqual(["POST", "/chat/threads/t1/resume/stream", { confirmation_id: "q1", answers: ["birch"] }]),
  );
});

test("questions can be declined in the owner's own words", async () => {
  const user = userEvent.setup();
  pending = questions;
  show();
  await user.click(await screen.findByRole("button", { name: "Answer in my own words" }));
  await user.type(screen.getByLabelText("Your answer"), "I'll measure tomorrow");
  await user.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(calls).toContainEqual(["POST", "/chat/threads/t1/resume/stream", { confirmation_id: "q1", declined: "I'll measure tomorrow" }]),
  );
});

test("a conversation reopened with questions pending shows the form from its first question", async () => {
  pending = questions;
  show();
  const form = within(await screen.findByRole("region", { name: "Questions" }));
  expect(form.getByText("Question 1 of 2")).toBeInTheDocument();
  expect(form.getByLabelText("Ceiling height?")).toBeInTheDocument();
  expect(screen.queryByLabelText("Message")).not.toBeInTheDocument();
});

test("the rail opens a flyout, switches, and closes on Escape and on its icon", async () => {
  const user = userEvent.setup();
  show();
  const projectIcon = await screen.findByRole("button", { name: "Project" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await user.click(projectIcon);
  expect(screen.getByRole("dialog", { name: "Project" })).toHaveFocus();
  expect(projectIcon).toHaveAttribute("aria-expanded", "true");

  await user.click(screen.getByRole("button", { name: "Brief" }));
  expect(screen.queryByRole("dialog", { name: "Project" })).not.toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "Brief" })).toBeInTheDocument();

  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Brief" })).toHaveFocus();

  await user.click(projectIcon);
  await user.click(projectIcon);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await user.click(projectIcon);
  await user.click(screen.getByRole("button", { name: "Close Project" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("the heading is renamed in place and an empty title is refused in words", async () => {
  const user = userEvent.setup();
  show();
  await user.click(await screen.findByRole("button", { name: "Rename" }));
  const field = screen.getByLabelText("Conversation title");
  await user.clear(field);
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(screen.getByRole("alert")).toHaveTextContent("A conversation needs a title.");
  expect(calls.some(([m]) => m === "PATCH")).toBe(false);

  await user.type(field, "Listening wall");
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("heading", { level: 2, name: "Listening wall" })).toBeInTheDocument();
  expect(calls).toContainEqual(["PATCH", "/chat/threads/t1", { title: "Listening wall" }]);
});

test("a title event updates the heading without a reload", async () => {
  const user = userEvent.setup();
  title = "";
  const live = controlledStream();
  turn = () => ({ events: live.stream });
  show();
  expect(await screen.findByRole("heading", { level: 2, name: "Untitled" })).toBeInTheDocument();
  await user.type(screen.getByLabelText("Message"), "I want a listening wall");
  await user.click(screen.getByRole("button", { name: "Send" }));
  live.send({ event: "specialist", data: { role: "intake" } });
  live.send({ event: "reply", data: { reply: "How wide?", specialists: ["intake"] } });
  live.send({ event: "title", data: { title: "Listening wall for records" } });
  expect(await screen.findByRole("heading", { level: 2, name: "Listening wall for records" })).toBeInTheDocument();
  title = "Listening wall for records";
  messages = [owner("I want a listening wall"), reply("How wide?")];
  live.send({ event: "done", data: {} });
  live.close();
  await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
});

test("a turn that fails while it runs gives the words back with the reason", async () => {
  const user = userEvent.setup();
  turn = () => ({
    events: [
      { event: "specialist", data: { role: "designer" } },
      { event: "error", data: { failure_class: "timeout", reason: "the model did not answer in time" } },
      { event: "done", data: {} },
    ],
  });
  show();
  await user.type(await screen.findByLabelText("Message"), "make it wider");
  await user.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("the model did not answer in time");
  expect(screen.getByLabelText("Message")).toHaveValue("make it wider");
  expect(within(screen.getByRole("region", { name: "Messages" })).queryByText("make it wider")).not.toBeInTheDocument();
});


const notice = (extra: Partial<Msg>): Msg => ({
  role: "notice", text: "The draft turntable of hall-bench version 1 is ready. You can also check it in the Project panel.",
  outcome: "succeeded", tier: "draft", package_id: "hall-bench", version: 1, ...extra,
});

test("the inspector opens from the address beside the chat, keeps the composer, and a layout without a piece hides it (Close)", async () => {
  const user = userEvent.setup();
  messages = [owner("a hall bench"), reply("How wide?")];
  show("/studio/workspace/t1?inspect=hall-bench/1");
  const inspector = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await inspector.findByText("Overall: W 1200 mm × H 450 mm × D 400 mm")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Messages" })).toBeInTheDocument();
  await user.type(screen.getByRole("textbox"), "two metres");
  expect(screen.getByRole("textbox")).toHaveValue("two metres");

  expect(inspector.queryByRole("button", { name: "Close inspector" })).not.toBeInTheDocument();
  act(() => setWorkspaceLayout("chat-room"));
  expect(screen.queryByRole("complementary", { name: "Inspector" })).not.toBeInTheDocument();
  expect(screen.getByRole("textbox")).toHaveValue("two metres");
});

test("a malformed inspect address is ignored and the piece pane shows the piece's latest version", async () => {
  messages = [reply("Hello")];
  show("/studio/workspace/t1?inspect=../etc/passwd");
  await screen.findByText("Hello");
  const inspector = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await inspector.findByText("Overall: W 1200 mm × H 450 mm × D 400 mm")).toBeInTheDocument();
  expect(calls.map(([, url]) => url).filter((url) => url.includes("passwd"))).toEqual([]);
});

test("a render notice names the tier on its Review button and opens the inspector on its Renders tab", async () => {
  const user = userEvent.setup();
  messages = [
    reply("Started a draft turntable of hall-bench version 1."),
    notice({}),
    notice({ text: "The draft still is ready.", tier: "draft", version: 2 }),
    notice({ text: "The final still is ready.", tier: "final", version: 3 }),
  ];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  expect(list.getByRole("button", { name: "Review draft v1" })).toBeInTheDocument();
  expect(list.getByRole("button", { name: "Review draft revision 2" })).toBeInTheDocument();
  expect(list.getByRole("button", { name: "Review final revision 3" })).toBeInTheDocument();

  // The newest draft render of version 1 is its still.
  await user.click(list.getByRole("button", { name: "Review draft v1" }));
  const inspector = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await inspector.findByRole("img", { name: "Still of hall-bench version 1" })).toBeInTheDocument();
  expect(inspector.getByRole("button", { name: "Renders", pressed: true })).toBeInTheDocument();

  // Another notice replaces the version shown; one not built yet is named in words.
  await user.click(list.getByRole("button", { name: "Review draft revision 2" }));
  expect(await inspector.findByText(/Version 2 is building/)).toBeInTheDocument();
});

test("Review final opens the Renders tab on the newest final render, a detailed turntable that plays", async () => {
  const user = userEvent.setup();
  messages = [notice({ text: "The final turntable of hall-bench version 4 is ready.", tier: "final", version: 4 })];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  await user.click(await list.findByRole("button", { name: "Review final revision 4" }));
  const inspector = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await inspector.findByRole("img", { name: "Detailed turntable, frame 1 of 36" })).toHaveAttribute(
    "src", "/packages/hall-bench/versions/4/files/detail/frames/0",
  );
  expect(inspector.getByRole("button", { name: /Detailed turntable/, pressed: true })).toBeInTheDocument();
});

test("a failed, shell or composition notice has no button", async () => {
  messages = [
    notice({ outcome: "failed", text: "The draft turntable of hall-bench version 2 did not finish, so nothing new was published. You can ask for it again.", tier: "draft", version: 2 }),
    notice({ text: "The draft turntable of the flat shell version 1 is ready.", package_id: undefined, version: undefined }),
  ];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  expect(await list.findByText(/did not finish/)).toBeInTheDocument();
  expect(list.getByText("The draft turntable of the flat shell version 1 is ready.")).toBeInTheDocument();
  expect(list.queryByRole("button", { name: /Review/ })).not.toBeInTheDocument();
});

test("a notice appears without a reload once the running render ends", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  messages = [reply("Started a draft turntable of hall-bench version 1.")];
  progressNow = progress(["brief", "piece", "built"], { rendering: true });
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  await list.findByText(/Started a draft turntable/);
  expect(list.queryByText(/is ready/)).not.toBeInTheDocument();

  messages = [...messages, notice({})];
  progressNow = progress(["brief", "piece", "built", "rendered"], { rendering: false });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3100);
  });
  expect(await list.findByText(/The draft turntable of hall-bench version 1 is ready/)).toBeInTheDocument();
});

test("the panel icons sit in the chat pane's header and name themselves on hover (Icons named)", async () => {
  messages = [reply("Hello")];
  show();
  await screen.findByText("Hello");
  const icons = screen.getByRole("navigation", { name: "Panels" });
  expect(icons).not.toHaveClass("sticky");
  expect(within(icons).getAllByRole("button").map((b) => b.getAttribute("title"))).toEqual([
    "Decisions so far", "Brief", "Project", "Piece", "Room",
  ]);
  // No Tools icon and no per-conversation tool switches (No Tools icon, studio-navigation-tidy).
  expect(screen.queryByRole("button", { name: "Tools" })).not.toBeInTheDocument();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(calls.some(([, url]) => url.includes("/tools"))).toBe(false);
  // In the header row with the title (the icons sit in its right-hand group with Layout), above the messages.
  const header = icons.parentElement!.parentElement!;
  expect(within(header).getByRole("heading", { level: 2, name: "Hall bench" })).toBeInTheDocument();
  expect(header).not.toContainElement(screen.getByRole("region", { name: "Messages" }));
});

test("the panel icons show their labels while the rails do (Expanded)", async () => {
  window.localStorage.setItem("studio.rail.expanded", "true");
  messages = [reply("Hello")];
  show();
  await screen.findByText("Hello");
  const icons = screen.getByRole("navigation", { name: "Panels" });
  expect(within(icons).getByText("Brief")).toBeInTheDocument();
  expect(within(icons).queryByRole("button", { name: "Hide labels" })).not.toBeInTheDocument();
});


// --- the inspector follows versions (app-check-2026-10-09) ---------------------------------

const version = (n: number, status: string) => ({ package_id: "hall-bench", version: n, status, approved_at: null, files: [] });

test("the split view follows a version created while it is open", async () => {
  let listed = [version(1, "succeeded")];
  let second = "queued";
  extra = (call) => {
    if (call === "GET /packages/hall-bench") return { body: { package_id: "hall-bench", versions: listed } };
    if (call === "GET /packages/hall-bench/versions/2")
      return { body: { ...version(2, second), files: second === "succeeded" ? ["model.glb", "spec.json"] : [] } };
    if (call === "GET /packages/hall-bench/versions/2/files/spec.json") return { body: SPEC };
  };
  messages = [owner("one more shelf"), reply("Revised.")];
  show("/studio/workspace/t1?inspect=hall-bench/1");
  const inspector = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await inspector.findByRole("combobox", { name: "Version" })).toHaveValue("1");

  // A confirmed revision creates version 2: within the poll, the view switches to it.
  listed = [version(2, "queued"), version(1, "succeeded")];
  expect(await inspector.findByRole("status", undefined, { timeout: 5000 })).toHaveTextContent("Showing version 2, the newest");
  expect(inspector.getByRole("combobox", { name: "Version" })).toHaveValue("2");
  expect(await inspector.findByText(/Version 2 is building/)).toBeInTheDocument();

  second = "succeeded";
  expect(await inspector.findByText("Overall: W 1200 mm × H 450 mm × D 400 mm", undefined, { timeout: 5000 })).toBeInTheDocument();
}, 15000);


// --- stop and edit (app-check-2026-10-09) ------------------------------------------------

test("Stop calls the stop route, shows the stop in words and frees the composer", async () => {
  const user = userEvent.setup();
  const live = controlledStream();
  turn = () => ({ events: live.stream });
  extra = (call) => (call === "POST /chat/threads/t1/turns/stop" ? { body: { stopping: true } } : undefined);
  show();
  await user.type(await screen.findByLabelText("Message"), "make it wider");
  await user.click(screen.getByRole("button", { name: "Send" }));
  live.send({ event: "specialist", data: { role: "designer" } });
  await user.click(await screen.findByRole("button", { name: "Stop" }));
  expect(calls.some(([m, url]) => m === "POST" && url === "/chat/threads/t1/turns/stop")).toBe(true);

  live.send({ event: "stopped", data: { text: "Stopped. This message and its replies were removed." } });
  live.send({ event: "done", data: {} });
  live.close();
  expect(await screen.findByText("Stopped. This message and its replies were removed.")).toBeInTheDocument();
  expect(screen.getByLabelText("Message")).toBeEnabled();
  expect(screen.getByLabelText("Message")).toHaveValue("make it wider");
  expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
});

test("Stop with no turn left on the server stops following the stream", async () => {
  const user = userEvent.setup();
  const live = controlledStream();
  turn = () => ({ events: live.stream });
  extra = (call) =>
    call === "POST /chat/threads/t1/turns/stop"
      ? { status: 409, body: { detail: { failure_class: "no_turn_running", reason: "no reply is being written" } } }
      : undefined;
  show();
  await user.type(await screen.findByLabelText("Message"), "make it wider");
  await user.click(screen.getByRole("button", { name: "Send" }));
  await user.click(await screen.findByRole("button", { name: "Stop" }));
  await waitFor(() => expect(screen.getByLabelText("Message")).toBeEnabled());
});

test("only the latest owner message offers Edit", async () => {
  messages = [
    { ...owner("first"), message_id: "m1" }, reply("One."),
    { ...owner("second"), message_id: "m2" }, reply("Two."),
    { ...owner("third"), message_id: "m3" }, reply("Three."),
  ];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  const edits = list.getAllByRole("button", { name: "Edit" });
  expect(edits).toHaveLength(1);
  expect(edits[0].closest("[data-side]")).toHaveTextContent("third");
});

test("Add to decisions opens the decisions table with the compressed message as a new row, and nothing is saved before Save", async () => {
  const user = userEvent.setup();
  messages = [{ ...owner("the shelves are 18 mm"), message_id: "m1" }, reply("Noted.")];
  extra = (call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: null, note: "- **Room:** Wohnen", owner_edited: false } };
    if (call === "PUT /chat/threads/t1/note") return { body: { package_id: null, note: "x", owner_edited: true } };
    if (call === "POST /chat/threads/t1/note/decision") return { body: { topic: "", decision: "Shelves are 18 mm" } };
    return undefined;
  };
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  const button = list.getAllByRole("button", { name: "Add to decisions" })[0];
  expect(button).toHaveClass("font-bold", "border-2", "bg-green-100");
  await user.click(button);
  expect(await screen.findByRole("textbox", { name: "New decision" })).toHaveValue("Shelves are 18 mm");
  expect(calls.find(([m, url]) => m === "POST" && url === "/chat/threads/t1/note/decision")?.[2]).toEqual({ text: "the shelves are 18 mm" });
  expect(calls.filter(([m, url]) => m === "PUT" && url === "/chat/threads/t1/note")).toHaveLength(0);
  await user.type(screen.getByRole("textbox", { name: "New topic" }), "Shelves");
  await user.click(screen.getByRole("button", { name: "Save" }));
  const saved = calls.find(([m, url]) => m === "PUT" && url === "/chat/threads/t1/note");
  expect(saved?.[2]).toEqual({ note: "- **Room:** Wohnen\n- **Shelves:** Shelves are 18 mm" });
});

test("the decisions note is read again when a turn ends", async () => {
  const user = userEvent.setup();
  messages = [{ ...owner("hello"), message_id: "m1" }, reply("Hi.")];
  turn = () => ({ events: replied("Done.", "designer") });
  extra = (call) =>
    call === "GET /chat/threads/t1/note" ? { body: { package_id: null, note: "- **Room:** Wohnen", owner_edited: false } } : undefined;
  show();
  await user.click(await screen.findByRole("button", { name: "Decisions so far" }));
  await screen.findByRole("table");
  const reads = () => calls.filter(([m, url]) => m === "GET" && url === "/chat/threads/t1/note").length;
  const before = reads();
  await user.type(await screen.findByLabelText("Message"), "remove the doors decision");
  await user.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(reads()).toBeGreaterThan(before));
});

test("no Edit while a confirmation is pending", async () => {
  messages = [{ ...owner("one more shelf"), message_id: "m1" }];
  pending = card;
  show();
  await screen.findByRole("region", { name: "Confirmation needed" });
  expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
});

test("Edit puts the message in the composer, warns, and sends to the latest-turn route", async () => {
  const user = userEvent.setup();
  messages = [{ ...owner("make it 60 cm deep"), message_id: "m1" }, reply("Which wall?")];
  turn = () => ({ events: [{ event: "rewound", data: { kept: ["Created bench version 3"] } }, ...replied("45 cm, noted.", "designer")] });
  show();
  await user.click(await screen.findByRole("button", { name: "Edit" }));
  const box = screen.getByLabelText("Message");
  expect(box).toHaveValue("make it 60 cm deep");
  expect(screen.getByRole("note")).toHaveTextContent(
    "Sending replaces this message and the replies after it. Builds or versions already made stay.",
  );
  await user.clear(box);
  await user.type(box, "make it 45 cm deep");
  await user.click(screen.getByRole("button", { name: "Send edit" }));
  const sent = calls.find(([m, url]) => m === "POST" && url === "/chat/threads/t1/turns/latest");
  expect(sent?.[2]).toEqual({ message_id: "m1", message: "make it 45 cm deep" });
  expect(await screen.findByText("Kept from the replaced message: Created bench version 3.")).toBeInTheDocument();
  expect(calls.some(([, url]) => url === "/chat/threads/t1/turns/stream")).toBe(false);
});

test("cancelling an edit sends nothing", async () => {
  const user = userEvent.setup();
  messages = [{ ...owner("make it 60 cm deep"), message_id: "m1" }, reply("Which wall?")];
  show();
  await user.click(await screen.findByRole("button", { name: "Edit" }));
  await user.click(screen.getByRole("button", { name: "Cancel edit" }));
  expect(screen.queryByRole("note")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Message")).toHaveValue("");
  expect(calls.some(([m]) => m === "POST")).toBe(false);
});


// --- versions: delete, limit, titles and build notices (version-cleanup-and-inspection) -----

test("the piece pane shows the version count near the limit (Near the limit)", async () => {
  progressNow = progress(["brief", "piece", "built"], { latest_version: 14, version_count: 14 });
  show("/studio/workspace/t1?inspect=hall-bench/1");
  const pane = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await pane.findByText("14 of 15 versions")).toBeInTheDocument();
});
test("no version count before the thirteenth version", async () => {
  progressNow = progress(["brief", "piece", "built"], { latest_version: 12, version_count: 12 });
  show("/studio/workspace/t1?inspect=hall-bench/1");
  const pane = within(await screen.findByRole("complementary", { name: "Inspector" }));
  await pane.findByText("succeeded");
  expect(pane.queryByText(/of 15 versions/)).not.toBeInTheDocument();
});
test("the shown version is deleted from the piece pane after Are you sure, and the pane shows the latest left (Delete from the piece pane)", async () => {
  const user = userEvent.setup();
  progressNow = progress(["brief", "piece", "built"], { latest_version: 4, version_count: 2 });
  extra = (call) => {
    if (call === "DELETE /packages/hall-bench/versions/4") {
      progressNow = progress(["brief", "piece", "built"]);
      // The stub's `json` cannot make a 204 with a body; an empty 200 stands in for it.
      return { body: {} };
    }
  };
  show("/studio/workspace/t1?inspect=hall-bench/4");
  const pane = within(await screen.findByRole("complementary", { name: "Inspector" }));
  await user.click(await pane.findByRole("button", { name: "Delete version 4" }));
  expect(calls.some(([m, u]) => m === "DELETE" && u === "/packages/hall-bench/versions/4")).toBe(false);
  await user.click(pane.getByRole("button", { name: "Yes, delete version 4" }));
  expect(await pane.findByRole("button", { name: "Delete version 1" })).toBeInTheDocument();
  expect(pane.queryByRole("button", { name: /version 4/ })).not.toBeInTheDocument();
  expect(calls.some(([m]) => m === "POST")).toBe(false);
});
test("no delete in the piece pane for an approved version", async () => {
  extra = (call) =>
    call === "GET /packages/hall-bench/versions/1"
      ? { body: { package_id: "hall-bench", version: 1, status: "succeeded", approved_at: "2026-10-10T00:00:00Z", files: ["model.glb", "spec.json"] } }
      : undefined;
  progressNow = progress(["brief", "piece", "built"], { approved_version: 1 });
  show("/studio/workspace/t1?inspect=hall-bench/1");
  const pane = within(await screen.findByRole("complementary", { name: "Inspector" }));
  await pane.findByRole("button", { name: "Unapprove version 1" });
  expect(pane.queryByRole("button", { name: /Delete version/ })).not.toBeInTheDocument();
});

test("a restyle look is kept from the piece pane, sending the owner's request (Keep a look from the piece pane)", async () => {
  const user = userEvent.setup();
  extra = (call) =>
    call === "GET /packages/hall-bench/versions/1/variants"
      ? { body: [{ id: "oak", label: "Oak", still: "/x.png", tier: "draft", note: null, looks: { carcass: "oak" } }] }
      : undefined;
  show("/studio/workspace/t1?inspect=hall-bench/1");
  const pane = within(await screen.findByRole("complementary", { name: "Inspector" }));
  await user.click(await pane.findByRole("button", { name: "Use this look" }));
  await waitFor(() =>
    expect(calls).toContainEqual([
      "POST",
      "/chat/threads/t1/turns/stream",
      expect.objectContaining({ message: expect.stringContaining('restyle picture "Oak" of hall-bench version 1') }),
    ]),
  );
});

test("the piece pane lists the open generator-extension requests", async () => {
  progressNow = progress(["brief", "piece", "built"], { open_requests: [{ field: "door.slats", request: "slatted doors" }] });
  show("/studio/workspace/t1?inspect=hall-bench/1");
  const pane = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await pane.findByText("Waiting on a generator extension")).toBeInTheDocument();
  expect(pane.getByText("door.slats")).toBeInTheDocument();
});
test("a build notice has an Inspect button that opens the inspector; a failed or deleted one has none", async () => {
  const user = userEvent.setup();
  messages = [
    reply("Created hall-bench version 1. The build has started."),
    { role: "notice", kind: "build", text: "hall-bench version 1 is built.", outcome: "succeeded", package_id: "hall-bench", version: 1 },
    { role: "notice", kind: "build", text: "hall-bench version 2 did not build. You can ask for it again.", outcome: "failed", package_id: "hall-bench", version: 2 },
    { role: "notice", kind: "build", text: "hall-bench version 3 is built.", outcome: "succeeded" },
  ];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  expect(await list.findByText("hall-bench version 1 is built.")).toBeInTheDocument();
  expect(list.getAllByRole("button", { name: /Inspect version/ })).toHaveLength(1);
  expect(list.queryByRole("button", { name: /Review/ })).not.toBeInTheDocument();
  await user.click(list.getByRole("button", { name: "Inspect version 1" }));
  const inspector = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await inspector.findByText("Overall: W 1200 mm × H 450 mm × D 400 mm")).toBeInTheDocument();
  expect(screen.getByRole("textbox")).toBeEnabled();
});

test("an old revision notice shows as text with no button, and a revision shows one build notice (Old revision notice, One notice per revision)", async () => {
  messages = [
    reply("Created hall-bench version 1."),
    { role: "notice", kind: "revision", text: "hall-bench version 1 is created.", outcome: "succeeded", package_id: "hall-bench", version: 1 },
    { role: "notice", kind: "build", text: "hall-bench version 1 is built.", outcome: "succeeded", package_id: "hall-bench", version: 1 },
  ];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  const old = await list.findByRole("region", { name: "Revision notice" });
  expect(old).toHaveTextContent("hall-bench version 1 is created.");
  expect(within(old).queryByRole("button")).not.toBeInTheDocument();
  expect(list.queryByRole("button", { name: "Open version 1" })).not.toBeInTheDocument();
  expect(list.getAllByRole("button", { name: "Inspect version 1" })).toHaveLength(1);
});

test("a build notice appears without a reload once the followed build ends", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  messages = [reply("Created hall-bench version 1. The build has started.")];
  progressNow = progress(["brief", "piece"], { build_status: "running" });
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  await list.findByText(/The build has started/);

  messages = [
    ...messages,
    { role: "notice", kind: "build", text: "hall-bench version 1 is built.", outcome: "succeeded", package_id: "hall-bench", version: 1 },
  ];
  progressNow = progress(["brief", "piece", "built"]);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3100);
  });
  expect(await list.findByRole("button", { name: "Inspect version 1" })).toBeInTheDocument();
});

// --- the messages box scrolls by itself (pieces-page-and-chat-scroll) --------------------

/** jsdom has no layout: the Messages box gets a stated scroll height and view height, and keeps its scrollTop. */
function boxGeometry(scrollHeight: number, clientHeight: number) {
  const geometry = { scrollHeight, clientHeight };
  const tops = new WeakMap<Element, number>();
  const isBox = (el: Element) => el.getAttribute("aria-label") === "Messages";
  const spies = [
    vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockImplementation(function (this: HTMLElement) {
      return isBox(this) ? geometry.scrollHeight : 0;
    }),
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockImplementation(function (this: HTMLElement) {
      return isBox(this) ? geometry.clientHeight : 0;
    }),
    vi.spyOn(Element.prototype, "scrollTop", "get").mockImplementation(function (this: Element) {
      return tops.get(this) ?? 0;
    }),
    vi.spyOn(Element.prototype, "scrollTop", "set").mockImplementation(function (this: Element, value: number) {
      tops.set(this, value);
    }),
  ];
  return { geometry, restore: () => spies.forEach((spy) => spy.mockRestore()) };
}

function scrollBoxTo(box: HTMLElement, top: number) {
  box.scrollTop = top;
  fireEvent.scroll(box);
}

test("the messages scroll in their own box with the composer below it", async () => {
  messages = [owner("a hall bench"), reply("How wide?")];
  show();
  const box = await screen.findByRole("region", { name: "Messages" });
  expect(box).toHaveClass("overflow-y-auto", "flex-1", "min-h-24");
  const composer = screen.getByLabelText("Message");
  expect(box).not.toContainElement(composer);
  const column = box.parentElement!;
  // The chat pane fills its pane of the layout; the panes fill the window below them.
  expect(column).toHaveClass("flex", "flex-col", "h-full");
  expect(column).toContainElement(composer);
});

test("a conversation opens at its last message", async () => {
  const { restore } = boxGeometry(2000, 400);
  try {
    messages = Array.from({ length: 30 }, (_, i) => (i % 2 ? reply(`reply ${i}`) : owner(`message ${i}`)));
    show();
    const box = await screen.findByRole("region", { name: "Messages" });
    await waitFor(() => expect(box.scrollTop).toBe(2000));
  } finally {
    restore();
  }
});

test("a reply is followed while the owner is at the bottom", async () => {
  const { geometry, restore } = boxGeometry(2000, 400);
  try {
    const user = userEvent.setup();
    const live = controlledStream();
    turn = () => ({ events: live.stream });
    messages = [owner("a hall bench"), reply("How wide?")];
    show();
    const box = await screen.findByRole("region", { name: "Messages" });
    await user.type(screen.getByLabelText("Message"), "1200 mm");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("status");
    messages = [...messages, owner("1200 mm"), reply("Noted: 1200 mm wide.")];
    geometry.scrollHeight = 2600;
    live.send({ event: "reply", data: { reply: "Noted: 1200 mm wide.", specialists: ["intake"] } });
    live.send({ event: "done", data: {} });
    live.close();
    expect(await screen.findByText("Noted: 1200 mm wide.")).toBeInTheDocument();
    await waitFor(() => expect(box.scrollTop).toBe(2600));
  } finally {
    restore();
  }
});

test("a reply does not move the box while the owner reads older messages", async () => {
  const { geometry, restore } = boxGeometry(2000, 400);
  try {
    const user = userEvent.setup();
    const live = controlledStream();
    turn = () => ({ events: live.stream });
    messages = [owner("a hall bench"), reply("How wide?")];
    show();
    const box = await screen.findByRole("region", { name: "Messages" });
    await user.type(screen.getByLabelText("Message"), "1200 mm");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("status");
    scrollBoxTo(box, 100);
    messages = [...messages, owner("1200 mm"), reply("Noted: 1200 mm wide.")];
    geometry.scrollHeight = 2600;
    live.send({ event: "reply", data: { reply: "Noted: 1200 mm wide.", specialists: ["intake"] } });
    live.send({ event: "done", data: {} });
    live.close();
    expect(await screen.findByText("Noted: 1200 mm wide.")).toBeInTheDocument();
    expect(box.scrollTop).toBe(100);
  } finally {
    restore();
  }
});

test("sending jumps to the bottom even when the owner had scrolled up", async () => {
  const { geometry, restore } = boxGeometry(2000, 400);
  try {
    const user = userEvent.setup();
    const live = controlledStream();
    turn = () => ({ events: live.stream });
    messages = [owner("a hall bench"), reply("How wide?")];
    show();
    const box = await screen.findByRole("region", { name: "Messages" });
    await waitFor(() => expect(box.scrollTop).toBe(2000));
    scrollBoxTo(box, 100);
    geometry.scrollHeight = 2300;
    await user.type(screen.getByLabelText("Message"), "1200 mm");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("status");
    expect(box.scrollTop).toBe(2300);
    live.close();
  } finally {
    restore();
  }
});

// --- the conversation's room beside the chat (project-room-inspection) ----------------------

const HALL = {
  name: "Hall", scope: "room", slug: "room-hall",
  model: "/compositions/room-hall/versions/1/files/model.glb",
  surfaces: "/compositions/room-hall/versions/1/files/report.json",
};

function serveRoom() {
  extra = (call) =>
    call === "GET /compositions/room-hall/versions/1/files/report.json"
      ? { body: { surfaces: { "wall 1": ["Wall_0_0"], ceiling: ["Ceiling"] }, extent_mm: { min: [0, 0, 0], max: [3000, 2000, 2500] } } }
      : undefined;
}

test("the Room icon opens the conversation's room in the room pane, switching the layout, and a layout change hides it (Room icon opens the room view, Close the room view)", async () => {
  const user = userEvent.setup();
  progressNow = progress(["brief", "piece", "built"], { room: HALL });
  serveRoom();
  messages = [reply("Hello")];
  show();
  await user.click(await screen.findByRole("button", { name: "Room" }));
  const pane = within(await screen.findByRole("complementary", { name: "Room view" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(pane.getByRole("heading", { name: "Hall" })).toBeInTheDocument();
  const switches = within(await pane.findByRole("group", { name: "Surfaces" }));
  expect(switches.getByRole("button", { name: "ceiling" })).toHaveAttribute("aria-pressed", "false");
  expect(screen.queryByRole("complementary", { name: "Inspector" })).not.toBeInTheDocument();
  expect(window.localStorage.getItem("studio.workspace.layout")).toBe("chat-room");
  await user.type(screen.getByRole("textbox"), "lower the shelf");
  expect(screen.getByRole("textbox")).toHaveValue("lower the shelf");

  act(() => setWorkspaceLayout("chat-piece"));
  expect(screen.queryByRole("complementary", { name: "Room view" })).not.toBeInTheDocument();
  expect(await screen.findByRole("complementary", { name: "Inspector" })).toBeInTheDocument();
  // The chat kept its half-typed message across the layout change.
  expect(screen.getByRole("textbox")).toHaveValue("lower the shelf");
});

test("with no room confirmed the Room icon shows the room pane, which says so (No room confirmed)", async () => {
  const user = userEvent.setup();
  progressNow = progress(["brief", "piece", "built"], { room: null });
  show();
  await user.click(await screen.findByRole("button", { name: "Room" }));
  expect(await screen.findByText("No room is confirmed yet in this conversation.")).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
test("the room view opens again from the address", async () => {
  // The layout is remembered, as after the owner chose it before the reload.
  setWorkspaceLayout("chat-room");
  progressNow = progress(["brief", "piece", "built"], { room: HALL });
  serveRoom();
  messages = [reply("Hello")];
  show("/studio/workspace/t1?room=room-hall");
  expect(await screen.findByRole("complementary", { name: "Room view" })).toBeInTheDocument();
});

test("a room address that is not the conversation's room is ignored and the room pane shows the current room", async () => {
  progressNow = progress(["brief", "piece", "built"], { room: HALL });
  serveRoom();
  setWorkspaceLayout("chat-room");
  messages = [reply("Hello")];
  show("/studio/workspace/t1?room=room-kitchen");
  await screen.findByText("Hello");
  const pane = within(await screen.findByRole("complementary", { name: "Room view" }));
  expect(pane.getByRole("heading", { name: "Hall" })).toBeInTheDocument();
});

test("in a layout with one side pane, opening the piece or the room switches to the layout that shows it (One pane at a time)", async () => {
  const user = userEvent.setup();
  progressNow = progress(["brief", "piece", "built"], { room: HALL });
  serveRoom();
  setWorkspaceLayout("chat-room");
  messages = [reply("Hello")];
  show("/studio/workspace/t1?room=room-hall");
  await screen.findByRole("complementary", { name: "Room view" });
  await user.click(screen.getByRole("button", { name: "Piece" }));
  expect(await screen.findByRole("complementary", { name: "Inspector" })).toBeInTheDocument();
  expect(screen.queryByRole("complementary", { name: "Room view" })).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Room" }));
  expect(await screen.findByRole("complementary", { name: "Room view" })).toBeInTheDocument();
  expect(screen.queryByRole("complementary", { name: "Inspector" })).not.toBeInTheDocument();
});

test("the room pane says in words why it shows no 3D view (No 3D view yet, No room confirmed)", async () => {
  setWorkspaceLayout("chat-room");
  progressNow = progress(["brief", "piece", "built"], { room: { ...HALL, slug: null, model: null, surfaces: null } });
  show();
  expect(await screen.findByText("Hall has no 3D view yet. Ask the Designer to compose the room.")).toBeInTheDocument();
  expect(screen.queryByRole("complementary", { name: "Room view" })).not.toBeInTheDocument();
  cleanup();

  progressNow = progress(["brief", "piece", "built"], { room: { ...HALL, model: null, surfaces: null } });
  show();
  expect(await screen.findByText("Composing Hall again adds the 3D view.")).toBeInTheDocument();
  cleanup();

  progressNow = progress(["brief", "piece", "built"], { room: null });
  show();
  expect(await screen.findByText("No room is confirmed yet in this conversation.")).toBeInTheDocument();
  expect(screen.queryByTestId("canvas")).not.toBeInTheDocument();
});

// --- room versions and the panel heading (project-room-inspection, after the owner's check) ---

const hallView = (version: number, extra: Record<string, unknown> = {}) => ({
  version, status: "succeeded", picture: null, viewer: null, items: [],
  model: `/compositions/room-hall/versions/${version}/files/model.glb`,
  surfaces: `/compositions/room-hall/versions/${version}/files/report.json`,
  dimensions: `/compositions/room-hall/versions/${version}/dimensions`,
  ...extra,
});
const VERSIONED_HALL = {
  ...HALL,
  model: "/compositions/room-hall/versions/3/files/model.glb",
  surfaces: "/compositions/room-hall/versions/3/files/report.json",
  versions: [hallView(3), hallView(2), hallView(1, { model: null, surfaces: null, dimensions: null })],
};

function serveHallVersions() {
  extra = (call) =>
    /^GET \/compositions\/room-hall\/versions\/\d\/files\/report\.json$/.test(call)
      ? { body: { surfaces: { "wall 1": ["Wall_0_0"], ceiling: ["Ceiling"] }, extent_mm: { min: [0, 0, 0], max: [3000, 2000, 2500] } } }
      : undefined;
}

test("the room pane offers its versions, keeps the chosen one in the address, and names one without 3D", async () => {
  // The layout is remembered, as after the owner chose it before the reload.
  setWorkspaceLayout("chat-room");
  const user = userEvent.setup();
  progressNow = progress(["brief", "piece", "built"], { room: VERSIONED_HALL });
  serveHallVersions();
  messages = [reply("Hello")];
  show("/studio/workspace/t1?room=room-hall");
  const pane = within(await screen.findByRole("complementary", { name: "Room view" }));
  const select = pane.getByRole("combobox", { name: "Version of Hall" });
  expect(select).toHaveValue("3");
  expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual(["Version 3", "Version 2", "Version 1"]);
  await pane.findByRole("group", { name: "Surfaces" });
  expect(pane.getByRole("button", { name: "dimensions" })).toHaveAttribute("aria-pressed", "false");

  await user.selectOptions(select, "1");
  expect(await pane.findByText("Version 1 of Hall has no 3D view. Composing Hall again adds it.")).toBeInTheDocument();
  await user.selectOptions(select, "2");
  await pane.findByRole("group", { name: "Surfaces" });
  expect(calls.some(([, url]) => url === "/compositions/room-hall/versions/2/files/report.json")).toBe(true);
});

test("a room address with a version shows it after a reload, and an unlisted one shows the latest", async () => {
  // The layout is remembered, as after the owner chose it before the reload.
  setWorkspaceLayout("chat-room");
  progressNow = progress(["brief", "piece", "built"], { room: VERSIONED_HALL });
  serveHallVersions();
  messages = [reply("Hello")];
  show("/studio/workspace/t1?room=room-hall/2");
  let pane = within(await screen.findByRole("complementary", { name: "Room view" }));
  expect(pane.getByRole("combobox", { name: "Version of Hall" })).toHaveValue("2");
  cleanup();

  show("/studio/workspace/t1?room=room-hall/9");
  pane = within(await screen.findByRole("complementary", { name: "Room view" }));
  expect(pane.getByRole("combobox", { name: "Version of Hall" })).toHaveValue("3");
});

test("unapproving a piece placed in an approved room shows the refusal in the piece pane", async () => {
  const user = userEvent.setup();
  extra = (call) => {
    if (call === "GET /packages/hall-bench/versions/1")
      return { body: { package_id: "hall-bench", version: 1, status: "succeeded", approved_at: "2026-10-10T00:00:00Z", files: ["model.glb", "spec.json"] } };
    if (call === "DELETE /packages/hall-bench/versions/1/approval")
      return {
        status: 409,
        body: {
          detail: {
            failure_class: "placed_in_approved_room",
            reason:
              "hall-bench version 1 is placed in the approved room composition Hall version 2; unapprove Hall version 2 first",
          },
        },
      };
  };
  progressNow = progress(["brief", "piece", "built"], {
    approved_version: 1,
    room: { ...HALL, approved_version: 2, versions: [hallView(2), hallView(1)] },
  });
  show("/studio/workspace/t1?inspect=hall-bench/1");
  const pane = within(await screen.findByRole("complementary", { name: "Inspector" }));
  await user.click(await pane.findByRole("button", { name: "Unapprove version 1" }));
  expect(await pane.findByText(/Hall version 2/)).toBeInTheDocument();
  expect(pane.getByRole("button", { name: "Unapprove version 1" })).toBeInTheDocument();
  expect(pane.queryByText(/409|placed_in_approved_room/)).not.toBeInTheDocument();
});
test("the room pane offers Delete version N for an unapproved version and none for the approved one", async () => {
  const user = userEvent.setup();
  setWorkspaceLayout("chat-room");
  progressNow = progress(["brief", "piece", "built"], {
    room: { ...VERSIONED_HALL, approved_version: 2, versions: [hallView(3), hallView(2, { approved_at: "2026-10-10T00:00:00Z" })] },
  });
  serveHallVersions();
  show("/studio/workspace/t1?room=room-hall");
  const pane = within(await screen.findByRole("complementary", { name: "Room view" }));
  expect(await pane.findByRole("button", { name: "Delete version 3" })).toBeInTheDocument();
  await user.selectOptions(pane.getByRole("combobox", { name: "Version of Hall" }), "2");
  await pane.findByRole("button", { name: "Unapprove version 2" });
  expect(pane.queryByRole("button", { name: /Delete version/ })).not.toBeInTheDocument();
});

test("a fresh room version becomes approvable without a reload (Fresh room version becomes approvable)", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  setWorkspaceLayout("chat-room");
  progressNow = progress(["brief", "piece", "built"], {
    room: { ...VERSIONED_HALL, versions: [hallView(3, { status: "running" }), hallView(2)] },
  });
  serveHallVersions();
  show("/studio/workspace/t1?room=room-hall");
  const pane = within(await screen.findByRole("complementary", { name: "Room view" }));
  await pane.findByRole("combobox", { name: "Version of Hall" });
  expect(pane.queryByRole("button", { name: "Approve version 3" })).not.toBeInTheDocument();

  progressNow = progress(["brief", "piece", "built"], { room: { ...VERSIONED_HALL, versions: [hallView(3), hallView(2)] } });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3100);
  });
  expect(await pane.findByRole("button", { name: "Approve version 3" })).toBeInTheDocument();
});

test("the room pane offers the chosen version's turntable viewer under its 3D view", async () => {
  setWorkspaceLayout("chat-room");
  const viewer = "/compositions/room-hall/versions/3/files/viewer.html";
  progressNow = progress(["brief", "piece", "built"], { room: { ...VERSIONED_HALL, versions: [hallView(3, { viewer }), hallView(2)] } });
  serveHallVersions();
  show("/studio/workspace/t1?room=room-hall");
  const pane = within(await screen.findByRole("complementary", { name: "Room view" }));
  expect(await pane.findByRole("link", { name: "Open the turntable viewer of Hall" })).toHaveAttribute("href", viewer);
});

// --- delete conversation (piece-conversation-link) ---------------------------------------

test("a confirmed delete removes the conversation and lands on Pieces", async () => {
  const user = userEvent.setup();
  title = "Hall shoe bench";
  messages = [reply("Hello")];
  show();
  await user.click(await screen.findByRole("button", { name: "Delete Hall shoe bench" }));
  const confirm = screen.getByRole("group", { name: "Delete Hall shoe bench?" });
  expect(confirm).toHaveTextContent("its pieces and renders are kept");
  expect(confirm).toHaveTextContent("cannot be restored");
  await user.click(within(confirm).getByRole("button", { name: "Delete" }));
  await waitFor(() => expect(calls).toContainEqual(["DELETE", "/chat/threads/t1", undefined]));
  expect(await screen.findByText("the pieces page")).toBeInTheDocument();
});

test("cancelling a delete sends nothing and keeps the conversation open", async () => {
  const user = userEvent.setup();
  title = "Hall shoe bench";
  messages = [reply("Hello")];
  show();
  await user.click(await screen.findByRole("button", { name: "Delete Hall shoe bench" }));
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByRole("heading", { name: "Hall shoe bench" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Delete Hall shoe bench" })).toBeInTheDocument();
  expect(calls.some(([method]) => method === "DELETE")).toBe(false);
});

test("a refused delete stays on the conversation and shows the reason", async () => {
  const user = userEvent.setup();
  title = "Hall shoe bench";
  messages = [reply("Hello")];
  extra = (call) =>
    call === "DELETE /chat/threads/t1"
      ? {
          status: 409,
          body: {
            detail: {
              failure_class: "turn_running",
              reason: "a reply is still being written in this conversation",
            },
          },
        }
      : undefined;
  show();
  await user.click(await screen.findByRole("button", { name: "Delete Hall shoe bench" }));
  await user.click(screen.getByRole("button", { name: "Delete" }));
  expect(await screen.findByText("a reply is still being written in this conversation")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Hall shoe bench" })).toBeInTheDocument();
  expect(screen.queryByText("the pieces page")).not.toBeInTheDocument();
});

test("Add to decisions opens an empty row with a message when the message cannot be compressed, never the full text", async () => {
  const user = userEvent.setup();
  messages = [{ ...owner("the shelves are 18 mm"), message_id: "m1" }, reply("Noted.")];
  extra = (call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: null, note: null, owner_edited: false } };
    if (call === "POST /chat/threads/t1/note/decision") return { body: { topic: "", decision: "" } };
    return undefined;
  };
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  await user.click(list.getAllByRole("button", { name: "Add to decisions" })[0]);
  expect(await screen.findByRole("textbox", { name: "New decision" })).toHaveValue("");
  expect(screen.getByText(/could not be compressed/)).toBeInTheDocument();
});

// --- the Brief panel (split-project-panel) ---

test("the Brief panel lists every setting and saves an edit", async () => {
  const user = userEvent.setup();
  show();
  const form = within(await openBrief());
  expect(await form.findByLabelText("Purpose")).toHaveValue("a bench by the door");
  expect(form.getByLabelText("Room")).toHaveValue("Hall");
  expect(form.getByLabelText("Highest the piece may be (mm)")).toHaveValue("900");
  expect(form.getByLabelText("Style")).toHaveValue("oak");
  expect(form.getByLabelText("Budget (EUR)")).toHaveValue("400");
  await user.clear(form.getByLabelText("Budget (EUR)"));
  await user.type(form.getByLabelText("Budget (EUR)"), "900");
  await user.selectOptions(form.getByLabelText("Room"), "Kitchen");
  await user.click(form.getByRole("button", { name: "Save" }));
  expect(await form.findByText("Saved.")).toBeInTheDocument();
  expect(calls).toContainEqual([
    "PUT",
    "/chat/threads/t1/brief",
    { room: "Kitchen", purpose: "a bench by the door", max_piece_height_mm: 900, style: "oak", budget_eur: 900 },
  ]);
  expect(form.getByLabelText("Budget (EUR)")).toHaveValue("900");
});

test("the Brief panel refuses an empty purpose in words and sends nothing", async () => {
  const user = userEvent.setup();
  show();
  const form = within(await openBrief());
  await user.clear(await form.findByLabelText("Purpose"));
  await user.click(form.getByRole("button", { name: "Save" }));
  expect(await form.findByText("The purpose is required.")).toBeInTheDocument();
  expect(calls.some(([method, url]) => method === "PUT" && url === "/chat/threads/t1/brief")).toBe(false);
});

test("the Brief panel shows a refusal from the service next to the form", async () => {
  const user = userEvent.setup();
  extra = (call) =>
    call === "PUT /chat/threads/t1/brief"
      ? { status: 409, body: { detail: { failure_class: "turn_running", reason: "a reply is still being written" } } }
      : undefined;
  show();
  const form = within(await openBrief());
  await user.click(await form.findByRole("button", { name: "Save" }));
  expect(await form.findByText(/a reply is still being written/)).toBeInTheDocument();
});

test("the Brief panel says so when there is no brief yet and shows no internals", async () => {
  briefNow = { ...briefNow, confirmed: false, room: null, purpose: null, max_piece_height_mm: null, style: null, budget_eur: null };
  show();
  const form = await openBrief();
  expect(await within(form).findByText(/No brief yet/)).toBeInTheDocument();
  expect(form.textContent).not.toMatch(/model|token|prompt|cost/i);
});

