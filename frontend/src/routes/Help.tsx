import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { cardClass } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Page } from "@/components/Page";
import { FieldError } from "../lib/form";
import { api, downloads, type HelpBlock, type HelpTopic } from "../lib/api";

/** A worked example: one room, its walls numbered from the starting corner, one door. */
function ExampleRoom() {
  return (
    <svg viewBox="0 0 320 240" role="img" aria-labelledby="example-room-title" className="w-full max-w-sm text-foreground">
      <title id="example-room-title">
        Example: a hall of 4000 by 3000 mm, walls numbered clockwise from the top-left corner, with a 900 mm door on wall 1
        starting 500 mm from the corner
      </title>
      <rect x="40" y="40" width="240" height="160" fill="none" stroke="currentColor" strokeWidth="6" />
      <line x1="70" y1="40" x2="124" y2="40" stroke="var(--background)" strokeWidth="8" />
      <path d="M70 40 A54 54 0 0 1 124 94" fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" />
      <circle cx="40" cy="40" r="5" fill="currentColor" />
      <g fontSize="12" fill="currentColor" textAnchor="middle">
        <text x="160" y="28">wall 1 · 4000 mm</text>
        <text x="300" y="124" transform="rotate(90 300 124)">wall 2 · 3000 mm</text>
        <text x="160" y="222">wall 3 · 4000 mm</text>
        <text x="20" y="124" transform="rotate(-90 20 124)">wall 4 · 3000 mm</text>
        <text x="97" y="60">door 900</text>
        <text x="160" y="125">Hall · ceiling 2500 mm</text>
      </g>
      <text x="46" y="58" fontSize="10" fill="currentColor">start</text>
    </svg>
  );
}

const STEP_HEIGHT = 34;
const STEP_GAP = 16;
/** The step a design file from the template joins: the Designer's (the third step). */
const IMPORT_JOINS = 2;

/**
 * How a piece is made, drawn from the workflow topic's own steps so the diagram, its text alternative and
 * the chat's answer say the same thing. The template import joins at the Designer's step.
 */
function WorkflowDiagram({ steps }: { steps: string[] }) {
  const pitch = STEP_HEIGHT + STEP_GAP;
  const height = steps.length * pitch - STEP_GAP + 2;
  const joinY = IMPORT_JOINS * pitch + STEP_HEIGHT / 2 + 1;
  return (
    <svg viewBox={`0 0 560 ${height}`} role="img" aria-labelledby="workflow-title" className="w-full max-w-2xl text-foreground">
      <title id="workflow-title">
        {`How a piece is made: ${steps.join(" Then: ")} A design file made from the template joins at the design step.`}
      </title>
      <defs>
        <marker id="workflow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0 0 L10 5 L0 10 z" fill="currentColor" />
        </marker>
      </defs>
      {steps.map((step, index) => {
        const y = index * pitch + 1;
        return (
          <g key={step}>
            <rect x="1" y={y} width="380" height={STEP_HEIGHT} rx="6" fill="none" stroke="currentColor" />
            <text x="191" y={y + STEP_HEIGHT / 2 + 4} fontSize="11" fill="currentColor" textAnchor="middle">
              {step}
            </text>
            {index < steps.length - 1 && (
              <line
                x1="191" y1={y + STEP_HEIGHT} x2="191" y2={y + pitch - 2}
                stroke="currentColor" markerEnd="url(#workflow-arrow)"
              />
            )}
          </g>
        );
      })}
      {steps.length > IMPORT_JOINS && (
        <g>
          <rect x="420" y={joinY - STEP_HEIGHT / 2} width="139" height={STEP_HEIGHT} rx="6" fill="none" stroke="currentColor" strokeDasharray="4 3" />
          <text x="489" y={joinY + 4} fontSize="11" fill="currentColor" textAnchor="middle">
            Design file (template)
          </text>
          <line x1="420" y1={joinY} x2="384" y2={joinY} stroke="currentColor" markerEnd="url(#workflow-arrow)" />
        </g>
      )}
    </svg>
  );
}

function Block({ block }: { block: HelpBlock }) {
  return (
    <>
      {block.heading && <h3>{block.heading}</h3>}
      {block.text && <p>{block.text}</p>}
      {block.items && (
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {block.items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </>
  );
}

/** The default prompt, shown whole so it can be selected by hand, with a button that copies it exactly. */
function CopyPrompt({ prompt }: { prompt: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(prompt);
      setState("copied");
      setTimeout(() => setState("idle"), 2000);
    } catch {
      setState("failed");
    }
  };
  return (
    <div className="space-y-2">
      <h3>The default prompt</h3>
      <pre className="whitespace-pre-wrap rounded-md border bg-muted p-3 text-sm">{prompt}</pre>
      <Button type="button" variant="outline" size="sm" onClick={copy}>
        {state === "copied" ? "Copied" : "Copy prompt"}
      </Button>
      {state === "failed" && <p className="text-sm text-destructive">Copy failed — select the text.</p>}
    </div>
  );
}

function Topic({ topic }: { topic: HelpTopic }) {
  const steps = topic.body.find((block) => block.items)?.items ?? [];
  return (
    <details className={cardClass}>
      <summary className="cursor-pointer font-heading text-lg">{topic.title}</summary>
      <div className="mt-3 space-y-3">
        {topic.body.map((block, index) => (
          <Block key={index} block={block} />
        ))}
        {topic.id === "blueprint" && <ExampleRoom />}
        {topic.id === "workflow" && <WorkflowDiagram steps={steps} />}
        {topic.download === "import_template" && (
          <p>
            <a href={downloads.importTemplate} download="import-template.json" className="underline">
              Download the import template
            </a>
          </p>
        )}
        {topic.prompt && <CopyPrompt prompt={topic.prompt} />}
      </div>
    </details>
  );
}

/** The Studio's help: one collapsed topic per entry of the help source, the same text the chat answers from. */
export default function Help() {
  const help = useQuery({ queryKey: ["help"], queryFn: api.help });
  return (
    <Page>
      <h1>Help</h1>
      {help.isError && <FieldError message="The help could not be loaded." />}
      {help.data?.topics.map((topic) => <Topic key={topic.id} topic={topic} />)}
    </Page>
  );
}
