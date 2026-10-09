import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import Conversation from "./Conversation";

// No WebGL in jsdom: the 3D stage is a stub that counts how often its module is loaded.
const canvas = vi.hoisted(() => ({ loaded: 0 }));
vi.mock("@/components/inspector/InspectorCanvas", () => {
  canvas.loaded += 1;
  return { default: () => <div data-testid="canvas" /> };
});

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
  kind?: "text" | "answers" | "render" | "build";
  rows?: { question: string; answer: string }[];
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

const tools = [
  { plugin: "room_fit", description: "Check whether a piece fits a room", enabled: true, toggleable: true },
  { plugin: "create_piece", description: "Create a new piece", enabled: true, toggleable: false },
];

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
      if (call === "GET /chat/threads/t1")
        return json({ body: { thread_id: "t1", title, package_id: null, created_at: "", last_turn_at: "", messages, pending } });
      if (call === "GET /chat/threads/t1/progress") return json({ body: progressNow });
      if (call === "GET /chat/threads/t1/tools") return json({ body: tools });
      if (call === "GET /packages/hall-bench/versions/1")
        return json({ body: { package_id: "hall-bench", version: 1, status: "succeeded", approved_at: null, files: ["model.glb", "spec.json"] } });
      if (call === "GET /packages/hall-bench/versions/1/files/spec.json") return json({ body: SPEC });
      if (call === "GET /packages/hall-bench/versions/2")
        return json({ body: { package_id: "hall-bench", version: 2, status: "queued", approved_at: null, files: [] } });
      if (call === "GET /chat/threads/t1/uploads")
        return json({ body: [{ upload_id: "u1", kind: "jpeg", size_bytes: 3, original_name: "blueprint.jpeg" }] });
      const approval = /^(PUT|DELETE) \/packages\/hall-bench\/versions\/(\d)\/approval$/.exec(call);
      if (approval) {
        const version = Number(approval[2]);
        progressNow = { ...(progressNow as object), approved_version: approval[1] === "PUT" ? version : null };
        return json({ body: { package_id: "hall-bench", version, status: "succeeded", approved_at: null } });
      }
      if (call === "PUT /chat/threads/t1/tools/room_fit") return json({ body: { ...tools[0], enabled: false } });
      if (call === "POST /chat/threads/t1/turns/stream") return streamed(await turn(body));
      if (call === "POST /chat/threads/t1/turns/latest") return streamed(await turn(body));
      if (call === "POST /chat/threads/t1/resume/stream") return streamed(await resume(body));
      if (call === "PATCH /chat/threads/t1") {
        title = String(body.title);
        return json({ body: { thread_id: "t1", title, package_id: null, created_at: "", last_turn_at: "" } });
      }
      if (call === "POST /chat/threads/t1/uploads") return json(upload());
      return json({ status: 404, body: { detail: "not found" } });
    }),
  );
});

afterEach(() => vi.useRealTimers());

async function openProject() {
  await userEvent.setup().click(await screen.findByRole("button", { name: "Project" }));
  return screen.findByRole("region", { name: "Project" });
}

async function openTools(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: "Tools" }));
}

function show(path = "/conversations/t1") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route path="/conversations/:threadId" element={<Conversation />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const card = { confirmation_id: "c1", subject: "revise", summary: "cabinet: 2 shelves → 3", proposal: {} };
const owner = (text: string) => ({ role: "owner" as const, text });
const reply = (text: string) => ({ role: "assistant" as const, text });

test("the history is shown in order", async () => {
  messages = [owner("a hall bench"), reply("How wide?")];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  expect(list.getByText("a hall bench")).toBeInTheDocument();
  expect(list.getByText("How wide?")).toBeInTheDocument();
});

test("the 3D stage is not loaded while no inspector is open", async () => {
  messages = [owner("a hall bench"), reply("How wide?")];
  show();
  await screen.findByText("How wide?");
  expect(canvas.loaded).toBe(0);
  expect(screen.queryByRole("complementary", { name: "Inspector" })).not.toBeInTheDocument();
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

test("the panel follows a build to its end without a reload", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  progressNow = progress(["brief", "piece"], { build_status: "running", next_step: "Wait for the build to finish" });
  show();
  const panel = within(await openProject());
  expect(await panel.findByText("running")).toBeInTheDocument();
  expect(panel.getByText(/Wait for the build to finish/)).toBeInTheDocument();

  progressNow = progress(["brief", "piece", "built"], { screenshot: "/packages/hall-bench/versions/1/files/screenshot.png" });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3100);
  });
  expect(await panel.findByText("succeeded")).toBeInTheDocument();
  expect(panel.getByRole("img", { name: /hall-bench/ })).toHaveAttribute("src", "/packages/hall-bench/versions/1/files/screenshot.png");
  expect(panel.getByText(/Ask for a draft render/)).toBeInTheDocument();
  const built = panel.getByText("Built").closest("li");
  expect(built).toHaveAttribute("data-done", "true");
});

test("open review items are counted and link to the piece's page", async () => {
  progressNow = progress(["brief", "piece", "built", "rendered", "reviewed"], { open_review_items: 2 });
  show();
  const panel = within(await openProject());
  expect(await panel.findByText(/2 open review items/)).toBeInTheDocument();
  expect(panel.getByRole("link", { name: "Open the piece's page" })).toHaveAttribute("href", "/pieces");
});

test("a finished turntable shows its still and offers no viewer link", async () => {
  progressNow = progress(["brief", "piece", "built", "rendered"], {
    screenshot: "/packages/hall-bench/versions/1/files/screenshot.png",
    still: "/packages/hall-bench/versions/1/files/still.png",
    viewer: "/packages/hall-bench/versions/1/files/viewer.html",
  });
  show();
  const panel = within(await openProject());
  expect(await panel.findByRole("img", { name: /hall-bench/ })).toHaveAttribute("src", "/packages/hall-bench/versions/1/files/still.png");
  expect(panel.queryByRole("link", { name: /viewer/ })).not.toBeInTheDocument();
});

test("no viewer link is offered before the turntable is published", async () => {
  progressNow = progress(["brief", "piece", "built"]);
  show();
  const panel = within(await openProject());
  await panel.findByText("Built");
  expect(panel.queryByRole("link", { name: /viewer/ })).not.toBeInTheDocument();
});

test("a built piece has an Inspect button that opens the split view, a building one does not", async () => {
  progressNow = progress(["brief", "piece", "built"]);
  show();
  const panel = within(await openProject());
  expect(panel.queryByRole("link", { name: /Inspect/ })).not.toBeInTheDocument();
  await userEvent.setup().click(await panel.findByRole("button", { name: "Inspect version 1" }));
  const inspector = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await inspector.findByText("Overall: W 1200 mm × H 450 mm × D 400 mm")).toBeInTheDocument();
  // The heading names the piece; the version is not part of it (version-cleanup-and-inspection).
  expect(await inspector.findByRole("heading", { name: "Hall bench" })).toBeInTheDocument();
});

test("no inspector link while the build is running", async () => {
  progressNow = progress(["brief", "piece"], { build_status: "running" });
  show();
  const panel = within(await openProject());
  await panel.findByText("Built");
  expect(panel.queryByRole("button", { name: /Inspect/ })).not.toBeInTheDocument();
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

test("the owner can switch a toggleable tool off", async () => {
  const user = userEvent.setup();
  show();
  await openTools(user);
  const checkbox = await screen.findByLabelText("room_fit");
  expect(checkbox).toBeChecked();
  await user.click(checkbox);
  expect(calls).toContainEqual(["PUT", "/chat/threads/t1/tools/room_fit", { enabled: false }]);
});

test("a non-toggleable tool is shown always on", async () => {
  show();
  await openTools(userEvent.setup());
  const checkbox = await screen.findByLabelText("create_piece");
  expect(checkbox).toBeChecked();
  expect(checkbox).toBeDisabled();
  expect(screen.getByText("Always on")).toBeInTheDocument();
});

test("the panel shows latest v5 beside approved v4 and approving v5 refreshes it without a reload", async () => {
  const user = userEvent.setup();
  progressNow = progress(["brief", "piece", "built"], { latest_version: 5, approved_version: 4 });
  show();
  await openProject();
  const panel = await screen.findByRole("group", { name: "Approval" });
  expect(await within(panel).findByRole("button", { name: "Approve version 5" })).toBeInTheDocument();
  expect(within(panel).getByText("Approved")).toBeInTheDocument();
  expect(within(panel).getByText("version 4")).toBeInTheDocument();
  await user.click(within(panel).getByRole("button", { name: "Approve version 5" }));
  await waitFor(() => expect(within(panel).queryByRole("button", { name: "Approve version 5" })).toBeNull());
  expect(within(panel).getByRole("button", { name: "Unapprove version 5" })).toBeInTheDocument();
  expect(calls.some(([m, u]) => m === "PUT" && u === "/packages/hall-bench/versions/5/approval")).toBe(true);
});

test("no approve control is offered while the latest version is still building", async () => {
  progressNow = progress(["brief", "piece"], { build_status: "running" });
  show();
  await openProject();
  const panel = await screen.findByRole("group", { name: "Approval" });
  expect(within(panel).getByText("No version approved yet.")).toBeInTheDocument();
  expect(within(panel).queryByRole("button")).toBeNull();
});

test("unapproving from the panel clears the approved version", async () => {
  const user = userEvent.setup();
  progressNow = progress(["brief", "piece", "built"], { approved_version: 1 });
  show();
  await openProject();
  const panel = await screen.findByRole("group", { name: "Approval" });
  await user.click(within(panel).getByRole("button", { name: "Unapprove version 1" }));
  expect(await within(panel).findByText("No version approved yet.")).toBeInTheDocument();
  expect(calls.some(([m]) => m === "DELETE")).toBe(true);
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

test("an answered confirmation stays in the history as one muted line", async () => {
  messages = [
    owner("a hall bench"),
    { role: "confirmation", text: "brief: Room Hall: 1200 × 3000 mm — no (make it 4 shelves)" },
    reply("Four shelves, then?"),
  ];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  const line = list.getByText("Answered: brief: Room Hall: 1200 × 3000 mm — no (make it 4 shelves)");
  expect(line).toHaveAttribute("data-role", "confirmation");
  expect(list.getByText("Four shelves, then?")).toBeInTheDocument();
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

  await user.click(screen.getByRole("button", { name: "Tools" }));
  expect(screen.queryByRole("dialog", { name: "Project" })).not.toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "Tools" })).toBeInTheDocument();

  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Tools" })).toHaveFocus();

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
  expect(await screen.findByRole("heading", { level: 1, name: "Listening wall" })).toBeInTheDocument();
  expect(calls).toContainEqual(["PATCH", "/chat/threads/t1", { title: "Listening wall" }]);
});

test("a title event updates the heading without a reload", async () => {
  const user = userEvent.setup();
  title = "";
  const live = controlledStream();
  turn = () => ({ events: live.stream });
  show();
  expect(await screen.findByRole("heading", { level: 1, name: "Untitled" })).toBeInTheDocument();
  await user.type(screen.getByLabelText("Message"), "I want a listening wall");
  await user.click(screen.getByRole("button", { name: "Send" }));
  live.send({ event: "specialist", data: { role: "intake" } });
  live.send({ event: "reply", data: { reply: "How wide?", specialists: ["intake"] } });
  live.send({ event: "title", data: { title: "Listening wall for records" } });
  expect(await screen.findByRole("heading", { level: 1, name: "Listening wall for records" })).toBeInTheDocument();
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

test("the inspector opens from the address beside the chat, keeps the composer, and closes", async () => {
  const user = userEvent.setup();
  messages = [owner("a hall bench"), reply("How wide?")];
  show("/conversations/t1?inspect=hall-bench/1");
  const inspector = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await inspector.findByText("Overall: W 1200 mm × H 450 mm × D 400 mm")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Messages" })).toBeInTheDocument();
  await user.type(screen.getByRole("textbox"), "two metres");
  expect(screen.getByRole("textbox")).toHaveValue("two metres");

  await user.click(inspector.getByRole("button", { name: "Close inspector" }));
  expect(screen.queryByRole("complementary", { name: "Inspector" })).not.toBeInTheDocument();
  expect(screen.getByRole("textbox")).toHaveValue("two metres");
});

test("a malformed inspect address opens nothing", async () => {
  messages = [reply("Hello")];
  show("/conversations/t1?inspect=../etc/passwd");
  await screen.findByText("Hello");
  expect(screen.queryByRole("complementary", { name: "Inspector" })).not.toBeInTheDocument();
});

test("a render notice names the tier on its Review button and opens the inspector", async () => {
  const user = userEvent.setup();
  messages = [
    reply("Started a draft turntable of hall-bench version 1."),
    notice({}),
    notice({ text: "The preview still is ready.", tier: "preview", version: 2 }),
    notice({ text: "The final still is ready.", tier: "final", version: 3 }),
  ];
  show();
  const list = within(await screen.findByRole("region", { name: "Messages" }));
  expect(list.getByRole("button", { name: "Review draft v1" })).toBeInTheDocument();
  expect(list.getByRole("button", { name: "Review preview revision 2" })).toBeInTheDocument();
  expect(list.getByRole("button", { name: "Review final revision 3" })).toBeInTheDocument();

  await user.click(list.getByRole("button", { name: "Review draft v1" }));
  const inspector = within(await screen.findByRole("complementary", { name: "Inspector" }));
  expect(await inspector.findByText("Overall: W 1200 mm × H 450 mm × D 400 mm")).toBeInTheDocument();

  // Another notice replaces the version shown; one not built yet is named in words.
  await user.click(list.getByRole("button", { name: "Review preview revision 2" }));
  expect(await inspector.findByText(/Version 2 is building/)).toBeInTheDocument();
});

test("a failed, shell or composition notice has no button", async () => {
  messages = [
    notice({ outcome: "failed", text: "The preview turntable of hall-bench version 2 did not finish, so nothing new was published. You can ask for it again.", tier: "preview", version: 2 }),
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

test("the rail sits at the screen's edge, outside the page's centred content", async () => {
  messages = [reply("Hello")];
  show();
  await screen.findByText("Hello");
  const rail = screen.getByRole("navigation", { name: "Panels" });
  expect(rail.closest("main")).toBeNull();
  expect(rail).toHaveClass("sticky");
  expect(screen.getByRole("main")).not.toHaveClass("max-w-5xl");
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
  show("/conversations/t1?inspect=hall-bench/1");
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

test("the panel header names the piece without its version", async () => {
  progressNow = progress(["brief", "piece", "built"], { latest_version: 14, version_count: 14 });
  show();
  const panel = await openProject();
  const header = within(panel).getByText("Hall bench").closest("p") as HTMLElement;
  expect(header).toHaveTextContent("hall-bench");
  expect(header).not.toHaveTextContent("version 14");
  expect(within(panel).getByText("14 of 15 versions")).toBeInTheDocument();
});

test("no version count before the thirteenth version", async () => {
  progressNow = progress(["brief", "piece", "built"], { latest_version: 12, version_count: 12 });
  show();
  const panel = within(await openProject());
  await panel.findByText("Built");
  expect(panel.queryByText(/of 15 versions/)).not.toBeInTheDocument();
});

test("the latest version is deleted from the panel after Are you sure, and its inspector closes", async () => {
  const user = userEvent.setup();
  progressNow = progress(["brief", "piece", "built"]);
  extra = (call) => {
    if (call === "DELETE /packages/hall-bench/versions/1") {
      progressNow = { ...progress([]), package_id: null, name: null, latest_version: null, build_status: null, version_count: 0 };
      // The stub's `json` cannot make a 204 with a body; an empty 200 stands in for it.
      return { body: {} };
    }
  };
  show("/conversations/t1?inspect=hall-bench/1");
  await screen.findByRole("complementary", { name: "Inspector" });
  const panel = within(await openProject());
  await user.click(await panel.findByRole("button", { name: "Delete version 1" }));
  expect(panel.getByText(/the whole piece will be deleted/)).toBeInTheDocument();
  expect(calls.some(([m, u]) => m === "DELETE" && u === "/packages/hall-bench/versions/1")).toBe(false);
  await user.click(panel.getByRole("button", { name: "Yes, delete version 1" }));
  expect(await panel.findByText("No piece yet.")).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByRole("complementary", { name: "Inspector" })).not.toBeInTheDocument());
});

test("no delete in the panel for an approved latest version or one still building", async () => {
  progressNow = progress(["brief", "piece", "built"], { approved_version: 1 });
  show();
  const panel = within(await openProject());
  await panel.findByRole("button", { name: "Unapprove version 1" });
  expect(panel.queryByRole("button", { name: /Delete version/ })).not.toBeInTheDocument();
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
