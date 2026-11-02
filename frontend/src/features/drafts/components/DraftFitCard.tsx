import { CircleAlert } from "lucide-react";

import { cardClasses } from "@/ui/surface";
import type { DraftFit } from "../model/draftFit";

/* How well the posting is answered, kept in view while the lines that answer it are
   edited: the share of requirements the facts meet, and each one they miss.

   The analysis step decided this; the draft step only reports it, so the reader tailoring
   a line knows which requirement is still open without going back a step to look. Nothing
   here gates anything - a gap is shown, not enforced, exactly as on the analysis step. */
export const DraftFitCard = ({ fit }: { fit: DraftFit }) => (
  <section aria-labelledby="draft-fit-heading" className={cardClasses("flex flex-col gap-2.5 p-4 max-lg:p-3.5")}>
    <div className="flex items-baseline justify-between gap-3">
      <h2 className="text-support font-medium text-cv-text-muted" id="draft-fit-heading">
        התאמה למשרה
      </h2>
      <p className="text-heading-sheet font-extrabold text-cv-text tabular-nums">
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
      <ul aria-label="דרישות שלא מתקיימות במלואן" className="flex flex-wrap gap-1.5">
        {fit.gaps.map((gap) => (
          <li
            className="inline-flex max-w-full items-center gap-1.5 rounded-pill border border-dashed border-cv-border-strong px-2.5 py-1 text-caption font-bold text-cv-text"
            key={gap.requirementId}
          >
            <CircleAlert aria-hidden="true" className="size-icon-sm shrink-0 text-cv-text-muted lg:hidden" />
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
