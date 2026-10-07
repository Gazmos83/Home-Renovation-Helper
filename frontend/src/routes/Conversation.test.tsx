import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import Conversation from "./Conversation";

type Msg = { role: "owner" | "assistant" | "confirmation"; text: string };
type Reply = { status?: number; body?: unknown };

const STEPS = ["brief", "piece", "built", "rendered", "reviewed", "detail", "final"];
function progress(done: string[], extra: Record<string, unknown> = {}) {
  return {
    package_id: "hall-bench", name: "Hall bench", latest_version: 1, approved_version: null, build_status: "succeeded",
    steps: STEPS.map((step) => ({ step, done: done.includes(step), detail: null })),
    next_step: "Ask for a draft render", open_review_items: 0, open_requests: [],
    screenshot: null, still: null, ...extra,
  };
}

const tools = [
  { plugin: "room_fit", description: "Check whether a piece fits a room", enabled: true, toggleable: true },
  { plugin: "create_piece", description: "Create a new piece", enabled: true, toggleable: false },
];

let messages: Msg[];
let pending: unknown;
let progressNow: unknown;
let turn: (body: Record<string, unknown>) => Promise<Reply> | Reply;
let resume: (body: Record<string, unknown>) => Reply;
let upload: () => Reply;
let calls: [string, string, unknown][];

const json = (reply: Reply) =>
  new Response(JSON.stringify(reply.body ?? {}), { status: reply.status ?? 200, headers: { "Content-Type": "application/json" } });

beforeEach(() => {
  messages = [];
  pending = null;
  progressNow = progress([]);
  calls = [];
  turn = () => ({ body: { reply: "ok", specialist: "intake", pending: null } });
  resume = () => ({ body: { reply: "ok", specialist: "designer", pending: null } });
  upload = () => ({ status: 201, body: { upload_id: "u1", kind: "jpeg", size_bytes: 3, original_name: "blueprint.jpeg" } });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo, init: RequestInit = {}) => {
      const url = String(input);
      const method = init.method ?? "GET";
      const body = typeof init.body === "string" ? JSON.parse(init.body) : init.body;
      calls.push([method, url, body]);
      const call = `${method} ${url}`;
      if (call === "GET /chat/threads/t1")
        return json({ body: { thread_id: "t1", title: "Hall bench", package_id: null, created_at: "", last_turn_at: "", messages, pending } });
      if (call === "GET /chat/threads/t1/progress") return json({ body: progressNow });
      if (call === "GET /chat/threads/t1/tools") return json({ body: tools });
      const approval = /^(PUT|DELETE) \/packages\/hall-bench\/versions\/(\d)\/approval$/.exec(call);
      if (approval) {
        const version = Number(approval[2]);
        progressNow = { ...(progressNow as object), approved_version: approval[1] === "PUT" ? version : null };
        return json({ body: { package_id: "hall-bench", version, status: "succeeded", approved_at: null } });
      }
      if (call === "PUT /chat/threads/t1/tools/room_fit") return json({ body: { ...tools[0], enabled: false } });
      if (call === "POST /chat/threads/t1/turns") return json(await turn(body));
      if (call === "POST /chat/threads/t1/resume") return json(resume(body));
      if (call === "POST /chat/threads/t1/uploads") return json(upload());
      return json({ status: 404, body: { detail: "not found" } });
    }),
  );
});

afterEach(() => vi.useRealTimers());

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/conversations/t1"]}>
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

test("sending shows the message at once, locks the composer, then shows the reply by role", async () => {
  const user = userEvent.setup();
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  turn = async (body) => {
    await gate;
    messages = [owner(String(body.message)), reply("How wide is the hall?")];
    return { body: { reply: "How wide is the hall?", specialist: "intake", pending: null } };
  };
  show();
  await user.type(await screen.findByLabelText("Message"), "I want a bench for the hall");
  await user.click(screen.getByRole("button", { name: "Send" }));

  const list = within(screen.getByRole("region", { name: "Messages" }));
  expect(list.getByText("I want a bench for the hall")).toBeInTheDocument();
  expect(screen.getByLabelText("Message")).toBeDisabled();
  expect(screen.getByRole("status")).toHaveTextContent("Waiting for the reply");

  release();
  expect(await list.findByText("How wide is the hall?")).toBeInTheDocument();
  expect(list.getByText("intake")).toBeInTheDocument();
  expect(list.getAllByText("I want a bench for the hall")).toHaveLength(1);
  await waitFor(() => expect(screen.getByLabelText("Message")).toBeEnabled());
  expect(calls).toContainEqual(["POST", "/chat/threads/t1/turns", { message: "I want a bench for the hall", upload_ids: [] }]);
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
    return { body: { reply: "Version 2 is created.", specialist: "designer", pending: null } };
  };
  show();
  await user.click(await screen.findByRole("button", { name: "Yes" }));
  expect(await screen.findByText("Version 2 is created.")).toBeInTheDocument();
  expect(await screen.findByLabelText("Message")).toBeInTheDocument();
  expect(calls).toContainEqual(["POST", "/chat/threads/t1/resume", { confirmation_id: "c1", answer: "yes" }]);
});

test("No sends the reason with the answer", async () => {
  const user = userEvent.setup();
  pending = card;
  resume = () => {
    pending = null;
    messages = [reply("Shall I make it 4 shelves?")];
    return { body: { reply: "Shall I make it 4 shelves?", specialist: "designer", pending: null } };
  };
  show();
  await user.type(await screen.findByLabelText("Reason (optional)"), "make it 4 shelves");
  await user.click(screen.getByRole("button", { name: "No" }));
  expect(await screen.findByText("Shall I make it 4 shelves?")).toBeInTheDocument();
  expect(calls).toContainEqual(["POST", "/chat/threads/t1/resume", { confirmation_id: "c1", answer: "no", reason: "make it 4 shelves" }]);
});

test("an attached plan is shown as a thumbnail and sent with the turn", async () => {
  const user = userEvent.setup();
  show();
  await user.upload(await screen.findByLabelText("Add a plan, photo or design"), new File(["x"], "blueprint.jpeg", { type: "image/jpeg" }));
  expect(await screen.findByRole("img", { name: "blueprint.jpeg" })).toHaveAttribute("src", "/uploads/u1");
  await user.type(screen.getByLabelText("Message"), "This is my flat");
  await user.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(calls).toContainEqual(["POST", "/chat/threads/t1/turns", { message: "This is my flat", upload_ids: ["u1"] }]),
  );
});

test("a refused upload shows the service's reason and attaches nothing", async () => {
  const user = userEvent.setup();
  upload = () => ({ status: 413, body: { detail: { failure_class: "too_large", reason: "the image is too large" } } });
  show();
  await user.upload(await screen.findByLabelText("Add a plan, photo or design"), new File(["x"], "huge.jpeg", { type: "image/jpeg" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("the image is too large");
  expect(screen.queryByRole("img", { name: "huge.jpeg" })).not.toBeInTheDocument();
});

test("the panel follows a build to its end without a reload", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  progressNow = progress(["brief", "piece"], { build_status: "running", next_step: "Wait for the build to finish" });
  show();
  const panel = within(await screen.findByRole("region", { name: "Project" }));
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
  const panel = within(await screen.findByRole("region", { name: "Project" }));
  expect(await panel.findByText(/2 open review items/)).toBeInTheDocument();
  expect(panel.getByRole("link", { name: "Open the piece's page" })).toHaveAttribute("href", "/pieces");
});

test("the owner can switch a toggleable tool off", async () => {
  const user = userEvent.setup();
  show();
  const checkbox = await screen.findByLabelText("room_fit");
  expect(checkbox).toBeChecked();
  await user.click(checkbox);
  expect(calls).toContainEqual(["PUT", "/chat/threads/t1/tools/room_fit", { enabled: false }]);
});

test("a non-toggleable tool is shown always on", async () => {
  show();
  const checkbox = await screen.findByLabelText("create_piece");
  expect(checkbox).toBeChecked();
  expect(checkbox).toBeDisabled();
  expect(screen.getByText("Always on")).toBeInTheDocument();
});

test("the panel shows latest v5 beside approved v4 and approving v5 refreshes it without a reload", async () => {
  const user = userEvent.setup();
  progressNow = progress(["brief", "piece", "built"], { latest_version: 5, approved_version: 4 });
  show();
  const panel = await screen.findByRole("group", { name: "Approval" });
  expect(await screen.findByText("version 5")).toBeInTheDocument();
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
  const panel = await screen.findByRole("group", { name: "Approval" });
  expect(within(panel).getByText("No version approved yet.")).toBeInTheDocument();
  expect(within(panel).queryByRole("button")).toBeNull();
});

test("unapproving from the panel clears the approved version", async () => {
  const user = userEvent.setup();
  progressNow = progress(["brief", "piece", "built"], { approved_version: 1 });
  show();
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
    await screen.findByLabelText("Add a plan, photo or design"),
    new File(['{"kind":"custom_build"}'], "wall-unit.json", { type: "application/json" }),
  );
  expect(await screen.findByLabelText("Design file wall-unit.json")).toHaveTextContent("wall-unit.json");
  expect(screen.queryByRole("img", { name: "wall-unit.json" })).not.toBeInTheDocument();
  await user.type(screen.getByLabelText("Message"), "Import this");
  await user.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(calls).toContainEqual(["POST", "/chat/threads/t1/turns", { message: "Import this", upload_ids: ["d1"] }]),
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
    await screen.findByLabelText("Add a plan, photo or design"),
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
