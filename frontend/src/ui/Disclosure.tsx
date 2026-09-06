import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

import { cx } from "./cx";

interface DisclosureProps {
  children: ReactNode;
  className?: string;
  summary: string;
}

/* Content that belongs to the screen but is longer than the screen's own text: the job
   posting the analysis was run against, the decision document behind an approved
   revision.

   It replaced `TechnicalDetails`, which collapsed two unlike things behind one label.
   Identifiers and failure codes are no longer shown at all, so what is left is content -
   and content is disclosed because it is long, not because it is technical. The summary
   is required for that reason: "פרטים טכניים" was a default that told the reader nothing
   about what opening it would produce.

   The mark is a real chevron that turns rather than the UA's own triangle: the triangle
   is drawn at the inline start on the reader's side of an RTL line, at a size and colour
   no token owns, and a row of them read as bullets instead of as controls. Closed it
   points along the reading direction (left, under RTL) and open it points down, so the
   state is a shape as well as a position. */
export const Disclosure = ({ children, className, summary }: DisclosureProps) => (
  <details className={cx("group text-support", className)}>
    <summary className="flex cursor-pointer list-none items-center gap-2 rounded-control font-medium text-cv-text-muted transition-colors hover:text-cv-text [&::-webkit-details-marker]:hidden">
      <ChevronDown
        aria-hidden="true"
        className="size-4 shrink-0 rotate-90 transition-transform duration-200 group-open:rotate-0"
      />
      <span>{summary}</span>
    </summary>
    <div className="mt-2 ps-6 leading-6 text-cv-text-muted">{children}</div>
  </details>
);
