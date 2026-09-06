import { Circle, CircleCheck } from "lucide-react";
import type { ReactNode } from "react";

import { cx } from "../../../ui/cx";

/* The bar that closes a tab: what is still missing on one side, the command on the other.

   It replaced a disabled button with a sentence under it that only appeared once the
   reader had scrolled past everything else. Pinned to the bottom of the viewport, the
   state of the decision and the control that commits it are read together at any scroll
   position - so "why is this disabled" is answered where the button is, not above it. */
export const PreparationActionBar = ({ children, primary }: { children?: ReactNode; primary: ReactNode }) => (
  <div className="sticky bottom-4 z-20 flex flex-wrap items-center justify-between gap-4 rounded-surface border border-cv-border bg-cv-surface/95 p-4 shadow-floating backdrop-blur-xl">
    <div className="flex min-w-0 flex-wrap items-center gap-x-5 gap-y-2">{children}</div>
    <div className="flex flex-wrap items-center gap-3">{primary}</div>
  </div>
);

export interface ChecklistEntry {
  done: boolean;
  label: string;
}

/* The live checklist. Colour is never the only signal (A.2): a done entry changes its
   mark from a ring to a ring with a tick, and states which it is in words for a reader
   who hears the list rather than sees it. */
export const PreparationChecklist = ({ entries, label }: { entries: readonly ChecklistEntry[]; label: string }) => (
  <ul aria-label={label} className="flex flex-wrap items-center gap-x-5 gap-y-2">
    {entries.map((entry) => (
      <li className="flex items-center gap-2 text-support font-medium" key={entry.label}>
        {entry.done ? (
          <CircleCheck aria-hidden="true" className="size-4 shrink-0 text-cv-success" />
        ) : (
          <Circle aria-hidden="true" className="size-4 shrink-0 text-cv-text-muted" />
        )}
        <span className={cx(entry.done ? "text-cv-text" : "text-cv-text-muted")}>{entry.label}</span>
        <span className="sr-only">{entry.done ? "הושלם" : "טרם הושלם"}</span>
      </li>
    ))}
  </ul>
);
