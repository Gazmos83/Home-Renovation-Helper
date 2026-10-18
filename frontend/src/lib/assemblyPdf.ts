import type { SpecAssemblyStep } from "./api";

/**
 * A built version's assembly steps as an A4 PDF, made in the browser (piece-assembly-steps).
 * The page building takes the few `jsPDF` calls it needs, so it is tested without the library.
 */

/** The `jsPDF` calls the layout uses. */
export type PdfPage = {
  setFont: (name: string, style: string) => unknown;
  setFontSize: (size: number) => unknown;
  text: (text: string | string[], x: number, y: number) => unknown;
  splitTextToSize: (text: string, width: number) => string[];
  addPage: () => unknown;
  save: (name: string) => unknown;
};

const MARGIN = 20;
const PAGE_HEIGHT = 297;
const WIDTH = 210 - 2 * MARGIN;
/** Indent of a step's body under its title, past the step number. */
const INDENT = 10;
/** Millimetres per line at 11 pt. */
const LINE = 5.5;

/** The saved name: `hall-bench-v2-assembly.pdf`. */
export function assemblyPdfName(packageId: string, version: number): string {
  return `${packageId}-v${version}-assembly.pdf`;
}

export function assemblyTitle(packageId: string, version: number): string {
  return `${packageId} – version ${version} – Assembly`;
}

/** Writes the title and every step in order onto `doc`, starting a page when the next block would not fit. */
export function writeAssembly(doc: PdfPage, packageId: string, version: number, steps: SpecAssemblyStep[]): void {
  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.text(assemblyTitle(packageId, version), MARGIN, MARGIN + 4);
  let y = MARGIN + 16;
  for (const step of steps) {
    doc.setFontSize(11);
    const body = doc.splitTextToSize(step.body, WIDTH - INDENT);
    // A step's title stays with at least its first body line.
    if (y + 2 * LINE > PAGE_HEIGHT - MARGIN) {
      doc.addPage();
      y = MARGIN + 4;
    }
    doc.setFont("helvetica", "bold");
    doc.text(`${String(step.step).padStart(2, "0")}  ${step.title}`, MARGIN, y);
    y += LINE;
    doc.setFont("helvetica", "normal");
    for (const line of body) {
      if (y > PAGE_HEIGHT - MARGIN) {
        doc.addPage();
        y = MARGIN + 4;
      }
      doc.text(line, MARGIN + INDENT, y);
      y += LINE;
    }
    y += LINE / 2;
  }
}

/** Makes the PDF and saves it; `jspdf` is loaded only now, outside the main bundle. */
export async function downloadAssemblyPdf(packageId: string, version: number, steps: SpecAssemblyStep[]): Promise<void> {
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  writeAssembly(doc, packageId, version, steps);
  doc.save(assemblyPdfName(packageId, version));
}
