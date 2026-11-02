import { cx } from "@/ui/cx";
import type { DraftPart } from "../model/draftParts";

interface DraftSectionNavProps {
  active: string;
  onSelect: (id: string) => void;
  parts: DraftPart[];
}

/* Which part of the CV is open. The editor shows one part at a time, as the design
   does: a tailored CV runs to sixty-odd lines, and one long scroll of every section put
   the line being decided pages away from the fit and the approval it bears on.

   One list, two shapes. On a wide screen it is a card of rows in the column at the
   editor's start, the open part marked and a dot on each part still holding a line to
   decide; on a phone it is the grey segmented track above the open part, scrolling
   sideways when a CV has more parts than fit. Buttons rather than in-page links: a press
   swaps the part on screen instead of scrolling to it. The other parts stay mounted,
   only hidden, so text typed into one survives a visit to another. */
export const DraftSectionNav = ({ active, onSelect, parts }: DraftSectionNavProps) => (
  <nav
    aria-label="חלקי קורות החיים"
    className="flex gap-0.5 lg:flex-col lg:rounded-control-lg lg:border lg:border-cv-hairline lg:bg-cv-surface lg:p-2 max-lg:gap-1 max-lg:overflow-x-auto max-lg:rounded-control max-lg:bg-cv-surface-muted max-lg:p-1"
  >
    {parts.map((part) => {
      const current = part.id === active;
      return (
        <button
          aria-current={current ? "true" : undefined}
          className={cx(
            "flex min-h-10 items-center justify-between gap-2 rounded-item px-3 text-start text-label transition-colors",
            "max-lg:min-h-9 max-lg:flex-1 max-lg:shrink-0 max-lg:justify-center max-lg:whitespace-nowrap max-lg:text-support",
            current
              ? "bg-cv-surface-muted font-bold text-cv-text max-lg:bg-cv-surface max-lg:shadow-segment"
              : "text-cv-text-muted hover:bg-cv-surface-muted hover:text-cv-text max-lg:font-medium max-lg:hover:bg-cv-surface",
          )}
          dir="auto"
          key={part.id}
          onClick={() => onSelect(part.id)}
          type="button"
        >
          {part.name}
          {part.pending ? (
            <>
              <span aria-hidden="true" className="size-2 shrink-0 rounded-pill bg-cv-text max-lg:hidden" />
              <span className="sr-only"> (שורה ממתינה להחלטה)</span>
            </>
          ) : null}
        </button>
      );
    })}
  </nav>
);
