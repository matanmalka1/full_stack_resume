import { ChevronLeft, Clock } from "lucide-react";
import { Link } from "react-router-dom";

import type { ApplicationDetail } from "@/api/contracts";
import { routePaths } from "@/navigation/routePaths";
import { buttonClasses } from "@/ui/Button";
import { formatDateTime } from "@/utils/formatDateTime";
import { isNextActionLate } from "../model/recruitmentLadder";

/* The reminder the reader set for this application, as the step's one dark block: what
   to do and when, or that it is late. It is drawn only when there is one - an empty dark
   card would be the loudest thing on the screen saying nothing.

   The arrow opens the recruitment manager, where the reminder is written and cleared;
   the card itself changes nothing.

   On a wide screen it heads the aside, stacked rather than in a row: the reminder named
   large, and under it the way to the draft once there is one - the reminder is usually
   about sending the CV, and the draft is where that work is. */
export const NextActionCard = ({ detail, onUpdate }: { detail: ApplicationDetail; onUpdate: () => void }) => {
  const { next_action: action, next_action_date: date } = detail.application;
  if (action == null || action.trim() === "") return null;

  const late = isNextActionLate(date);
  const when = late ? "באיחור" : date == null ? null : formatDateTime(date, "date");
  const hasDraft = detail.document_id != null;

  return (
    <section
      aria-labelledby="next-action-heading"
      className="relative flex items-center gap-3 rounded-surface bg-cv-accent p-3 text-cv-on-accent shadow-floating lg:flex-col lg:items-start lg:gap-3 lg:p-5"
    >
      <span
        aria-hidden="true"
        className="flex size-11 shrink-0 items-center justify-center rounded-control border border-cv-on-accent/25 lg:hidden"
      >
        <Clock className="size-icon-lg" />
      </span>
      <div className="min-w-0 flex-1 lg:pe-10">
        <h2 className="text-caption font-medium opacity-80" id="next-action-heading">
          הפעולה הבאה
          {when === null ? null : <span className={late ? "font-bold" : undefined}> · {when}</span>}
        </h2>
        <p className="line-clamp-2 text-body font-bold lg:mt-1 lg:text-heading-sm lg:font-extrabold" dir="auto">
          {action}
        </p>
      </div>
      {hasDraft ? (
        <Link
          className={buttonClasses("secondary", "border-transparent max-lg:hidden")}
          to={routePaths.draft(detail.application.id)}
        >
          מעבר לטיוטה
        </Link>
      ) : null}
      <button
        aria-label="עדכון הפעולה הבאה"
        className="flex size-11 shrink-0 items-center justify-center rounded-control bg-cv-surface text-cv-text transition-colors hover:bg-cv-surface-muted lg:absolute lg:end-3 lg:top-3 lg:size-9"
        onClick={onUpdate}
        type="button"
      >
        <ChevronLeft aria-hidden="true" className="size-icon-lg lg:size-icon-md" />
      </button>
    </section>
  );
};
