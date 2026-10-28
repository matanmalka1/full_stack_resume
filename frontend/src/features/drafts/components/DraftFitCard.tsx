import { CircleAlert } from "lucide-react";

import { cx } from "@/ui/cx";

import type { DraftFit } from "../model/draftFit";

/* How well the posting is answered, kept in view while the lines that answer it are
   edited: the share of requirements the facts meet, and each one they miss.

   The analysis step decided this; the draft step only reports it, so the reader tailoring
   a line knows which requirement is still open without going back a step to look. Nothing
   here gates anything - a gap is shown, not enforced, exactly as on the analysis step.

   On a phone it opens the step. From the large breakpoint, `beside` makes it the step
   grid's end column next to the workspace (see the page's `bodyClassName`), pinned while
   the lines scroll past it - the `!` overrides the grid's default of spanning both
   columns. Without it, it opens the step there too, across the full width: the split
   workspace needs the row's whole width for the lines and the document. */
export const DraftFitCard = ({ beside, fit }: { beside: boolean; fit: DraftFit }) => (
  <section
    aria-labelledby="draft-fit-heading"
    className={cx(
      "flex flex-col gap-3 rounded-surface border border-cv-border bg-cv-surface p-card-padding lg:border-cv-hairline lg:shadow-card",
      beside && "lg:sticky lg:top-6 lg:order-1 lg:col-span-1! lg:col-start-2!",
    )}
  >
    <div className="flex items-baseline justify-between gap-3">
      <h2 className="text-support font-semibold text-cv-text-muted" id="draft-fit-heading">
        התאמה למשרה
      </h2>
      <p className="text-heading-md font-bold text-cv-text tabular-nums">
        <span className="sr-only">{`${fit.matched} מתוך ${fit.total} דרישות מתקיימות`}</span>
        <span aria-hidden="true" dir="ltr">{`${fit.matched}/${fit.total}`}</span>
      </p>
    </div>

    {/* Drawn only: the figure above is the value, and a second announcement of it as a
        progress bar would say the same thing twice. */}
    <div aria-hidden="true" className="h-2 overflow-hidden rounded-pill bg-cv-surface-muted">
      <div className="h-full rounded-pill bg-cv-accent" style={{ width: `${(fit.matched / fit.total) * 100}%` }} />
    </div>

    {fit.gaps.length === 0 ? null : (
      <ul aria-label="דרישות שלא מתקיימות במלואן" className="flex flex-wrap gap-2">
        {fit.gaps.map((gap) => (
          <li
            className="inline-flex max-w-full items-center gap-1.5 rounded-pill border border-dashed border-cv-border-strong px-3 py-1 text-support font-semibold text-cv-text"
            key={gap.requirementId}
          >
            <CircleAlert aria-hidden="true" className="size-icon-sm shrink-0 text-cv-text-muted" />
            <span className="truncate" title={gap.requirement}>
              {gap.severity === "hard" ? "חסר: " : "חלקי: "}
              <span dir="auto">{gap.requirement}</span>
            </span>
          </li>
        ))}
      </ul>
    )}
  </section>
);
