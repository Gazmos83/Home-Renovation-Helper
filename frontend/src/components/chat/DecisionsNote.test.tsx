import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import { DecisionsNote } from "./DecisionsNote";

function show(props: { prefill?: { topic: string; decision: string; failed?: boolean }; compressing?: boolean; onPrefillUsed?: () => void } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DecisionsNote threadId="t1" {...props} />
    </QueryClientProvider>,
  );
}

test("a note that cannot be read says so instead of loading forever", async () => {
  stubFetch((call) => (call === "GET /chat/threads/t1/note" ? { status: 503, body: { detail: "down" } } : undefined));
  show();
  expect(await screen.findByText("The note could not be read.")).toBeInTheDocument();
  expect(screen.queryByText("Loading…")).not.toBeInTheDocument();
});

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

test("Add Topic Decision appends a row to the note and there is no Correct button", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note")
      return { body: { package_id: "hall-bench", note: "## Figures\n- doors: hinged", owner_edited: false } };
    if (call === "PUT /chat/threads/t1/note")
      return { body: { package_id: "hall-bench", note: "saved", owner_edited: true } };
  });
  show();
  const user = userEvent.setup();
  await screen.findByRole("table");
  expect(screen.queryByRole("button", { name: "Correct" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Add Topic Decision" }));
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  await user.type(screen.getByRole("textbox", { name: "New topic" }), "Handles");
  await user.type(screen.getByRole("textbox", { name: "New decision" }), "push-latch");
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(calls).toContainEqual([
    "PUT",
    "/chat/threads/t1/note",
    { note: "## Figures\n- doors: hinged\n- **Handles:** push-latch" },
  ]);
  expect(await screen.findByText("Corrected by you.")).toBeInTheDocument();
});

test("a note-less conversation can add its first row", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: null, note: null, owner_edited: false } };
    if (call === "PUT /chat/threads/t1/note") return { body: { package_id: null, note: "x", owner_edited: true } };
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add Topic Decision" }));
  await user.type(screen.getByRole("textbox", { name: "New topic" }), "Room");
  await user.type(screen.getByRole("textbox", { name: "New decision" }), "Wohnen");
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(calls).toContainEqual(["PUT", "/chat/threads/t1/note", { note: "- **Room:** Wohnen" }]);
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

test("the note is a table by heading, without a Decisions so far title", async () => {
  stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note")
      return {
        body: {
          package_id: null,
          note: "# Decisions So Far\n\n## Rooms and figures\n- wall: 3 m wide\n- height: 2.4 m\n\n## Open questions\n- door side",
          owner_edited: false,
        },
      };
  });
  show();
  expect(await screen.findByRole("table")).toBeInTheDocument();
  expect(screen.getAllByRole("row")).toHaveLength(4);
  expect(screen.getByRole("cell", { name: "wall: 3 m wide" })).toBeInTheDocument();
  expect(screen.queryByText(/decisions so far/i)).not.toBeInTheDocument();
});

test("rows are shown five to a page", async () => {
  const note = "## Everything\n" + Array.from({ length: 7 }, (_, i) => `- decision ${i + 1}`).join("\n");
  stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: null, note, owner_edited: false } };
  });
  show();
  const user = userEvent.setup();
  expect(await screen.findByText("Page 1 of 2")).toBeInTheDocument();
  expect(screen.getByText("decision 5")).toBeInTheDocument();
  expect(screen.queryByText("decision 6")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByText("decision 7")).toBeInTheDocument();
  expect(screen.queryByText("decision 5")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Previous" }));
  expect(screen.getByText("decision 1")).toBeInTheDocument();
});

test("a bold label opens its own topic and the bold marks are not shown", async () => {
  stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note")
      return { body: { package_id: null, note: "## Figures\n- **Room:** Wohnen, **2500 mm** ceiling", owner_edited: false } };
  });
  show();
  expect(await screen.findByRole("cell", { name: "Room" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Wohnen, 2500 mm ceiling" })).toBeInTheDocument();
});

test("a row is edited in the table and only its line changes", async () => {
  const note = "## Figures\n- **Room:** Wohnen\n- ceiling 2500 mm\n- doors: hinged";
  const calls = stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: null, note, owner_edited: false } };
    if (call === "PUT /chat/threads/t1/note") return { body: { package_id: null, note: "saved", owner_edited: true } };
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Edit Room" }));
  const box = screen.getByRole("textbox", { name: "Decision" });
  await user.clear(box);
  await user.type(box, "Wohnen v2");
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(calls).toContainEqual([
    "PUT",
    "/chat/threads/t1/note",
    { note: "## Figures\n- **Room:** Wohnen v2\n- ceiling 2500 mm\n- doors: hinged" },
  ]);
  expect(await screen.findByText("Corrected by you.")).toBeInTheDocument();
});

test("changing the topic of a heading row writes it as a label; cancel changes nothing", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note")
      return { body: { package_id: null, note: "## Figures\n- ceiling 2500 mm", owner_edited: false } };
    if (call === "PUT /chat/threads/t1/note") return { body: { package_id: null, note: "x", owner_edited: true } };
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Edit Figures" }));
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(calls.filter((c) => c[0] === "PUT")).toHaveLength(0);
  await user.click(screen.getByRole("button", { name: "Edit Figures" }));
  const topic = screen.getByRole("textbox", { name: "Topic" });
  await user.clear(topic);
  await user.type(topic, "Height");
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(calls).toContainEqual(["PUT", "/chat/threads/t1/note", { note: "## Figures\n- **Height:** ceiling 2500 mm" }]);
});

test("Delete removes one row after confirming, and a heading left empty goes with it", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note")
      return { body: { package_id: null, note: "## Figures\n- **Room:** Wohnen\n## Doors\n- hinged", owner_edited: false } };
    if (call === "PUT /chat/threads/t1/note") return { body: { package_id: null, note: "x", owner_edited: true } };
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Delete Doors" }));
  await user.click(screen.getByRole("button", { name: "Keep" }));
  expect(calls.filter((c) => c[0] === "PUT")).toHaveLength(0);
  await user.click(screen.getByRole("button", { name: "Delete Doors" }));
  await user.click(screen.getByRole("button", { name: "Confirm delete Doors" }));
  expect(calls).toContainEqual(["PUT", "/chat/threads/t1/note", { note: "## Figures\n- **Room:** Wohnen" }]);
});

test("the only row cannot be deleted", async () => {
  stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: null, note: "- **Room:** Wohnen", owner_edited: false } };
  });
  show();
  expect(await screen.findByRole("button", { name: "Delete Room" })).toBeDisabled();
});

test("a message offered from the chat opens a new row with its text; the owner gives the topic and saves", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: null, note: "- **Room:** Wohnen", owner_edited: false } };
    if (call === "PUT /chat/threads/t1/note") return { body: { package_id: null, note: "x", owner_edited: true } };
  });
  let used = 0;
  show({ prefill: { topic: "Shelves", decision: "Shelves are 18 mm" }, onPrefillUsed: () => (used += 1) });
  const user = userEvent.setup();
  expect(await screen.findByRole("textbox", { name: "New decision" })).toHaveValue("Shelves are 18 mm");
  expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
  expect(calls.filter((c) => c[0] === "PUT")).toHaveLength(0);
  expect(screen.getByRole("textbox", { name: "New topic" })).toHaveValue("Shelves");
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(calls).toContainEqual(["PUT", "/chat/threads/t1/note", { note: "- **Room:** Wohnen\n- **Shelves:** Shelves are 18 mm" }]);
  expect(used).toBe(1);
});

test("cancelling an offered message saves nothing", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: null, note: null, owner_edited: false } };
  });
  let used = 0;
  show({ prefill: { topic: "", decision: "Doors hinged" }, onPrefillUsed: () => (used += 1) });
  await userEvent.setup().click(await screen.findByRole("button", { name: "Cancel" }));
  expect(calls.filter((c) => c[0] === "PUT")).toHaveLength(0);
  expect(used).toBe(1);
});

test("Save is disabled until a topic is given", async () => {
  stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: null, note: null, owner_edited: false } };
  });
  show({ prefill: { topic: "", decision: "Doors hinged" } });
  expect(await screen.findByRole("textbox", { name: "New decision" })).toHaveValue("Doors hinged");
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
});

test("a message that could not be compressed opens an empty row with a message", async () => {
  stubFetch((call) => {
    if (call === "GET /chat/threads/t1/note") return { body: { package_id: null, note: null, owner_edited: false } };
  });
  show({ prefill: { topic: "", decision: "", failed: true } });
  expect(await screen.findByRole("textbox", { name: "New decision" })).toHaveValue("");
  expect(screen.getByText(/could not be compressed/)).toBeInTheDocument();
});
