import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { Notice } from "./Notice";

test("a finished room render links to its viewer in a new tab, with no Review button", () => {
  render(
    <Notice
      m={{
        role: "notice", kind: "render", outcome: "succeeded", tier: "draft",
        text: "The draft turntable of wohnen version 11 is ready. You can also find it on the Rooms page.",
        links: [{ label: "Open the turntable viewer", href: "/compositions/wohnen/versions/11/files/viewer.html" }],
      }}
      onReview={vi.fn()}
    />,
  );
  const link = screen.getByRole("link", { name: "Open the turntable viewer" });
  expect(link).toHaveAttribute("href", "/compositions/wohnen/versions/11/files/viewer.html");
  expect(link).toHaveAttribute("target", "_blank");
  expect(screen.queryByRole("button")).toBeNull();
});

test("a piece render's notice keeps its Review button and has no link", () => {
  render(
    <Notice
      m={{ role: "notice", kind: "render", outcome: "succeeded", tier: "draft", package_id: "hall-bench", version: 1,
           text: "The draft turntable of hall-bench version 1 is ready." }}
      onReview={vi.fn()}
    />,
  );
  expect(screen.getByRole("button", { name: "Review draft v1" })).toBeInTheDocument();
  expect(screen.queryByRole("link")).toBeNull();
});

test("a failed render shows no link even if one is sent", () => {
  render(
    <Notice
      m={{ role: "notice", kind: "render", outcome: "failed", tier: "draft", text: "It did not finish.",
           links: [{ label: "Open the still", href: "/x" }] }}
      onReview={vi.fn()}
    />,
  );
  expect(screen.queryByRole("link")).toBeNull();
});
