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
   about what opening it would produce. */
export const Disclosure = ({ children, className, summary }: DisclosureProps) => (
  <details className={cx("text-support", className)}>
    <summary className="cursor-pointer rounded-control font-medium text-cv-text-muted">
      {summary}
    </summary>
    <div className="mt-2 leading-6 text-cv-text-muted">{children}</div>
  </details>
);
