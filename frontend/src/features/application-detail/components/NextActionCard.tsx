import { ChevronLeft, Clock } from "lucide-react";

import type { ApplicationDetail } from "@/api/contracts";
import { formatDateTime } from "@/utils/formatDateTime";
import { isNextActionLate } from "../model/recruitmentLadder";

/* The reminder the reader set for this application, as the step's one dark block: what
   to do and when, or that it is late. It is drawn only when there is one - an empty dark
   card would be the loudest thing on the screen saying nothing.

   The arrow opens the recruitment manager, where the reminder is written and cleared;
   the card itself changes nothing. */
export const NextActionCard = ({ detail, onUpdate }: { detail: ApplicationDetail; onUpdate: () => void }) => {
  const { next_action: action, next_action_date: date } = detail.application;
  if (action == null || action.trim() === "") return null;

  const late = isNextActionLate(date);
  const when = late ? "באיחור" : date == null ? null : formatDateTime(date, "date");

  return (
    <section
      aria-labelledby="next-action-heading"
      className="flex items-center gap-3 rounded-surface bg-cv-accent p-3 text-cv-on-accent shadow-floating"
    >
      <span
        aria-hidden="true"
        className="flex size-11 shrink-0 items-center justify-center rounded-control border border-cv-on-accent/25"
      >
        <Clock className="size-icon-lg" />
      </span>
      <div className="min-w-0 flex-1">
        <h2 className="text-caption font-medium opacity-80" id="next-action-heading">
          הפעולה הבאה
          {when === null ? null : <span className={late ? "font-bold" : undefined}> · {when}</span>}
        </h2>
        <p className="line-clamp-2 text-body font-bold" dir="auto">
          {action}
        </p>
      </div>
      <button
        aria-label="עדכון הפעולה הבאה"
        className="flex size-11 shrink-0 items-center justify-center rounded-control bg-cv-surface text-cv-text transition-colors hover:bg-cv-surface-muted"
        onClick={onUpdate}
        type="button"
      >
        <ChevronLeft aria-hidden="true" className="size-icon-lg" />
      </button>
    </section>
  );
};
