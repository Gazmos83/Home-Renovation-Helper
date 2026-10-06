import * as React from "react";
import { cn } from "@/lib/utils";

/** The card look for elements that must stay a `section` or `form`. */
const cardClass =
  "rounded-xl border bg-card p-5 text-card-foreground shadow-sm [&_label]:mb-1.5 [&_label]:mt-3 [&_input]:block";

function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-slot="card" className={cn("flex flex-col gap-4 rounded-xl border bg-card p-5 text-card-foreground shadow-sm", className)} {...props} />
  );
}
function CardTitle({ className, ...props }: React.ComponentProps<"h2">) {
  return <h2 data-slot="card-title" className={cn("text-base font-semibold leading-none", className)} {...props} />;
}
function CardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return <p data-slot="card-description" className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

export { Card, cardClass, CardTitle, CardDescription };
