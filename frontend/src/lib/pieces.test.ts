import { expect, test } from "vitest";
import type { VersionInfo } from "./api";
import { pictureVersion } from "./pieces";

type Options = { approved?: boolean; status?: string; screenshot?: boolean };

function info(version: number, { approved = false, status = "succeeded", screenshot }: Options = {}): VersionInfo {
  const shot = screenshot ?? status === "succeeded";
  return {
    package_id: "bench",
    version,
    status,
    approved_at: approved ? "2026-10-09T10:00:00+00:00" : null,
    files: shot ? ["model.glb", "screenshot.png", "spec.json"] : ["spec.json"],
  };
}

test("the approved version is shown", () => {
  expect(pictureVersion([info(3), info(2, { approved: true }), info(1)])).toEqual({ version: 2, approved: true });
});

test("with none approved the newest built version is shown", () => {
  expect(pictureVersion([info(3), info(2), info(1)])).toEqual({ version: 3, approved: false });
});

test("a newest version that failed or is building is passed over", () => {
  expect(pictureVersion([info(5, { status: "failed" }), info(4, { status: "running" }), info(3)])).toEqual({
    version: 3,
    approved: false,
  });
});

test("an approved version without a screenshot falls back to the newest that has one", () => {
  expect(pictureVersion([info(3), info(2, { approved: true, screenshot: false })])).toEqual({ version: 3, approved: false });
});

test("nothing built, or nothing loaded yet, gives no picture", () => {
  expect(pictureVersion([info(1, { status: "running" })])).toBeNull();
  expect(pictureVersion([undefined, undefined])).toBeNull();
});
