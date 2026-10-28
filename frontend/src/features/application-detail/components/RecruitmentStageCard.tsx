import type { ApplicationDetail } from "@/api/contracts";
import { recruitmentStatusLabel } from "@/features/recruitment";
import { Button } from "@/ui/Button";
import { cx } from "@/ui/cx";
import { recruitmentRung } from "../model/recruitmentLadder";

/* Where the application stands with the employer, as one card at the top of the step:
   the status, its rung on a segmented bar, and what comes next.

   The CV work and the employer's answer move on two axes, and this screen is the CV's.
   The card is here because a reader on a phone opens an application from the board and
   asks both questions at once; it states the second without claiming the first depends
   on it, and changing it stays the recruitment manager's job - "עדכון" opens the same
   dialog the board does. */
export const RecruitmentStageCard = ({ detail, onUpdate }: { detail: ApplicationDetail; onUpdate: () => void }) => {
  const rung = recruitmentRung(detail.recruitment_status);
  const label = recruitmentStatusLabel(detail.recruitment_status);

  return (
    <section
      aria-labelledby="recruitment-stage-heading"
      className="flex flex-col gap-3 rounded-surface border border-cv-border bg-cv-surface p-4"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-support text-cv-text-muted" id="recruitment-stage-heading">
          שלב הגיוס
        </h2>
        <Button className="rounded-pill max-lg:min-h-11" onClick={onUpdate} size="compact" variant="secondary">
          עדכון
          <span className="sr-only"> שלב הגיוס</span>
        </Button>
      </div>
      <p className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-heading-sm font-extrabold text-cv-text">{label}</span>
        {rung.index === null ? null : (
          <span className="text-support text-cv-text-muted">
            · שלב {rung.index + 1} מתוך {rung.total}
          </span>
        )}
      </p>
      {/* The bar draws what the sentence above already says, so it is hidden from
          assistive tech. A closed process leaves every segment empty. */}
      <div aria-hidden="true" className="grid grid-cols-5 gap-1.5">
        {Array.from({ length: rung.total }, (_, index) => (
          <span
            className={cx(
              "h-1.5 rounded-pill",
              rung.index !== null && index <= rung.index ? "bg-cv-accent" : "bg-cv-border",
            )}
            key={index}
          />
        ))}
      </div>
      <div className="flex justify-between gap-2 text-caption text-cv-text-muted">
        <span aria-hidden="true">{rung.first}</span>
        {rung.next === null ? null : <span>הבא: {rung.next}</span>}
        <span aria-hidden="true">{rung.last}</span>
      </div>
    </section>
  );
};
