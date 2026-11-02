import { createElement } from "react";

import type { ApplicationDetail } from "@/api/contracts";
import { recruitmentStatusIcon, recruitmentStatusLabel } from "@/features/recruitment";
import { cx } from "@/ui/cx";
import { cardClasses } from "@/ui/surface";
import { recruitmentRung, recruitmentRungLabels } from "../model/recruitmentLadder";

/* Where the application stands with the employer, as the hub's first card: the status,
   its rung on a five-segment bar, and what comes next.

   The CV work and the employer's answer move on two axes, and the card states the second
   without claiming the first depends on it. Changing it is the status sheet's job: on a
   phone the card's own "עדכון" opens it; a wide screen has "עדכון סטטוס" in the header
   and draws the card as the ladder alone, every rung named under its segment.

   The rung names group statuses - an assignment is one of the interviews - so where the
   exact status is not the rung's own name a wide screen still says it, at the heading's
   end. A closed process leaves every segment empty and is named by its status. */
export const RecruitmentStageCard = ({ detail, onUpdate }: { detail: ApplicationDetail; onUpdate: () => void }) => {
  const rung = recruitmentRung(detail.recruitment_status);
  const label = recruitmentStatusLabel(detail.recruitment_status);
  /* The status's own mark, drawn through `createElement`: the icon is looked up per
     status, not a component of this file. */
  const statusIcon = (className: string) =>
    createElement(recruitmentStatusIcon(detail.recruitment_status), { "aria-hidden": true, className });
  const exactDiffers = rung.index === null || recruitmentRungLabels[rung.index] !== label;

  return (
    <section
      aria-labelledby="recruitment-stage-heading"
      className={cardClasses("flex flex-col gap-3 p-3.5 lg:gap-3.5 lg:p-5")}
    >
      <div className="flex min-h-8 items-center justify-between gap-3">
        <h2
          className="text-support font-medium text-cv-text-muted lg:text-body lg:font-extrabold lg:text-cv-text"
          id="recruitment-stage-heading"
        >
          שלב הגיוס
        </h2>
        <button
          className="inline-flex h-8 items-center rounded-pill border border-cv-border bg-cv-surface px-3 text-support font-bold text-cv-text transition-colors hover:bg-cv-surface-muted lg:hidden"
          onClick={onUpdate}
          type="button"
        >
          עדכון
          <span className="sr-only"> שלב הגיוס</span>
        </button>
        {exactDiffers ? (
          <span className="inline-flex items-center gap-1.5 text-support font-bold text-cv-text max-lg:hidden">
            {statusIcon("size-icon-sm")}
            {label}
          </span>
        ) : null}
      </div>

      {/* The phone's sentence: the exact status and its place on the ladder. */}
      <p className="flex flex-wrap items-center gap-x-2 text-heading-card font-extrabold text-cv-text lg:hidden">
        {statusIcon("size-icon-lg shrink-0")}
        {label}
        {rung.index === null ? null : (
          <span className="text-support font-medium text-cv-text-muted">
            · שלב {rung.index + 1} מתוך {rung.total}
          </span>
        )}
      </p>

      {/* The ladder. On a phone it draws what the sentence above already says, so it is
          hidden from assistive tech there, with its two ends and the next rung under it;
          a wide screen names every rung and marks the current one. */}
      <ol aria-label="שלבי הגיוס" className="grid grid-cols-5 gap-1 lg:gap-1.5">
        {recruitmentRungLabels.map((rungLabel, index) => {
          const current = rung.index === index;
          return (
            <li aria-current={current ? "step" : undefined} className="flex flex-col gap-2" key={rungLabel}>
              <span
                aria-hidden="true"
                className={cx(
                  "h-1.5 rounded-pill",
                  rung.index !== null && index <= rung.index ? "bg-cv-accent" : "bg-cv-border",
                )}
              />
              <span
                className={cx(
                  "text-support max-lg:sr-only",
                  current ? "font-extrabold text-cv-text" : "text-cv-text-muted",
                )}
              >
                {rungLabel}
              </span>
            </li>
          );
        })}
      </ol>
      <div aria-hidden="true" className="flex justify-between gap-2 text-caption text-cv-text-muted lg:hidden">
        <span>{rung.first}</span>
        {rung.next === null ? null : <span>הבא: {rung.next}</span>}
        <span>{rung.last}</span>
      </div>
    </section>
  );
};
