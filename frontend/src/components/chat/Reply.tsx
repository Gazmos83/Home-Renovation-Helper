import type { ComponentProps, ReactNode } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

// A render file's route in a reply: a piece's, a composition's or a shell's, and nothing
// else, so a reply cannot send the owner to another site. A route is made of ids, version
// numbers and file names only, so quotes or backticks around it and a trailing full stop
// are not part of it.
const FILE_ROUTE = /(?<![\w:/.[(])(\/(?:packages|compositions|apartments)\/[\w./-]*?\/files\/[\w./-]*[\w/-])/;
const WHOLE_ROUTE = new RegExp(`^${FILE_ROUTE.source.replace("(?<![\\w:/.[(])", "")}$`);
// Images only from the app's own routes.
const IMAGE_ROUTES = ["/packages/", "/compositions/", "/apartments/", "/uploads/"];

/** Whether `href` is a render file route of this app. */
export function isFileRoute(href: string | undefined): href is string {
  return Boolean(href && WHOLE_ROUTE.test(href));
}

/** A bare file route in the text becomes a Markdown link; code spans and fences are left alone. */
function linkRoutes(text: string): string {
  return text
    .split(/(```[\s\S]*?(?:```|$)|`[^`\n]*`)/)
    .map((part, index) => (index % 2 === 1 ? part : part.replace(new RegExp(FILE_ROUTE.source, "g"), "[$1]($1)")))
    .join("");
}

function RouteLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer noopener" className="underline">
      {children}
    </a>
  );
}

function codeText(children: ReactNode): string {
  return Array.isArray(children) ? children.join("") : String(children ?? "");
}

const components: Components = {
  // Only the app's own file routes are links; any other address is plain text.
  a: ({ href, children }) => (isFileRoute(href) ? <RouteLink href={href}>{children}</RouteLink> : <span>{children}</span>),
  img: ({ src, alt }) =>
    typeof src === "string" && IMAGE_ROUTES.some((prefix) => src.startsWith(prefix)) ? (
      <img src={src} alt={alt ?? ""} className="max-h-64 rounded-md border" />
    ) : (
      <span>{alt}</span>
    ),
  pre: ({ node, children }) => {
    const first = node?.children[0];
    const classes = first && first.type === "element" ? first.properties.className : undefined;
    if (Array.isArray(classes) && classes.includes("language-calc")) {
      return (
        <figure aria-label="Calculation" className="rounded-md border-2 bg-muted/40 px-4 py-3">
          <pre className="whitespace-pre-wrap font-mono text-sm">{children}</pre>
        </figure>
      );
    }
    return <pre className="overflow-x-auto rounded-md bg-muted px-3 py-2 text-sm">{children}</pre>;
  },
  code: ({ className, children }) => {
    const text = codeText(children);
    if (!className && isFileRoute(text)) return <RouteLink href={text}>{text}</RouteLink>;
    return <code className={className ?? "rounded bg-muted px-1 py-0.5 text-[0.9em]"}>{children}</code>;
  },
  table: ({ children }) => <Table>{children}</Table>,
  thead: ({ children }) => <TableHeader>{children}</TableHeader>,
  tbody: ({ children }) => <TableBody>{children}</TableBody>,
  tr: ({ children }) => <TableRow>{children}</TableRow>,
  th: ({ children, style }: ComponentProps<"th">) => <TableHead style={style}>{children}</TableHead>,
  td: ({ children, style }: ComponentProps<"td">) => <TableCell style={style}>{children}</TableCell>,
  ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
  h1: ({ children }) => <h3 className="text-lg">{children}</h3>,
  h2: ({ children }) => <h3 className="text-base">{children}</h3>,
  h3: ({ children }) => <h3 className="text-base">{children}</h3>,
};

/**
 * A reply as formatted text: headings, lists, tables, emphasis and code. Raw HTML stays
 * text and is never rendered; a `calc` block is a framed box of its own.
 */
export function Reply({ text }: { text: string }) {
  return (
    <div className="space-y-3 font-chat leading-relaxed [&_p]:text-base [&_p]:leading-relaxed">
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {linkRoutes(text)}
      </Markdown>
    </div>
  );
}
