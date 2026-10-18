import { expect, test } from "vitest";
import { assemblyPdfName, writeAssembly, type PdfPage } from "./assemblyPdf";

/** A fake page that records each text call and page break; it wraps a body every 30 characters. */
function fakePage() {
  const calls: (string | { text: string; y: number })[] = [];
  const page: PdfPage = {
    setFont: () => undefined,
    setFontSize: () => undefined,
    text: (text, _x, y) => calls.push({ text: String(text), y }),
    splitTextToSize: (text) => text.match(/.{1,30}(\s|$)/g)!.map((line) => line.trim()),
    addPage: () => calls.push("page"),
    save: () => undefined,
  };
  return { page, calls };
}

const texts = (calls: ReturnType<typeof fakePage>["calls"]) =>
  calls.map((call) => (typeof call === "string" ? call : call.text));

test("the title comes first and the steps follow in order, numbered with two digits", () => {
  const { page, calls } = fakePage();
  writeAssembly(page, "hall-bench", 2, [
    { step: 1, title: "Cut and edge-band", body: "Cut and label every part." },
    { step: 2, title: "Install", body: "Position, level and fix the build in place." },
  ]);
  expect(texts(calls)).toEqual([
    "hall-bench – version 2 – Assembly",
    "01  Cut and edge-band",
    "Cut and label every part.",
    "02  Install",
    "Position, level and fix the",
    "build in place.",
  ]);
});

test("a long sequence starts new pages and keeps every line on the page", () => {
  const { page, calls } = fakePage();
  const steps = Array.from({ length: 30 }, (_, index) => ({
    step: index + 1,
    title: `Step ${index + 1}`,
    body: "Fix the top and bottom between the sides with confirmats and glue.",
  }));
  writeAssembly(page, "wardrobe", 1, steps);
  expect(calls.filter((call) => call === "page").length).toBeGreaterThan(0);
  for (const call of calls) if (typeof call !== "string") expect(call.y).toBeLessThanOrEqual(297 - 20);
  expect(texts(calls).filter((text) => /^\d\d {2}Step/.test(text))).toHaveLength(30);
  // A title is never the last line of a page.
  texts(calls).forEach((text, index, all) => {
    if (/^\d\d {2}Step/.test(text)) expect(all[index + 1]).not.toBe("page");
  });
});

test("the file is saved under the piece and version", () => {
  expect(assemblyPdfName("hall-bench", 2)).toBe("hall-bench-v2-assembly.pdf");
});
