import { ChevronLeft, Clock } from "lucide-react";

import type { ApplicationDetail } from "@/api/contracts";
import { formatDate } from "@/utils/formatDateTime";
import { isNextActionLate } from "../model/recruitmentLadder";

/* The reminder the reader set for this application, as the hub's one dark block: what to
   do and when, or that it is late. It is drawn only when there is one - an empty dark
   card would be the loudest thing on the screen saying nothing.

   On a phone it is a row under the stage card, its arrow the way to change it; a wide
   screen stands it at the top of the side column with the command written out. Both open
   the status sheet, where the reminder is written and cleared; the card changes nothing. */
export const NextActionCard = ({
  detail,
  headingId,
  onUpdate,
}: {
  detail: ApplicationDetail;
  /* The hub draws the card once per width, each instance under its own heading id. */
  headingId: string;
  onUpdate: () => void;
}) => {
  const { next_action: action, next_action_date: date } = detail.application;
  if (action == null || action.trim() === "") return null;

  const late = isNextActionLate(date);
  const when = late ? "באיחור" : date == null ? null : formatDate(date);

  return (
    <section
      aria-labelledby={headingId}
      className="flex items-center gap-3 rounded-surface bg-cv-accent p-3.5 text-cv-on-accent shadow-floating lg:flex-col lg:items-stretch lg:gap-2.5 lg:p-4.5"
    >
      <span
        aria-hidden="true"
        className="flex size-10 shrink-0 items-center justify-center rounded-control bg-cv-on-accent/15 lg:hidden"
      >
        <Clock className="size-icon-lg" />
      </span>
      <div className="min-w-0 flex-1">
        <h2 className="text-caption font-medium opacity-85" id={headingId}>
          הפעולה הבאה
          {when === null ? null : <span className={late ? "font-bold" : undefined}> · {when}</span>}
        </h2>
        <p className="line-clamp-2 text-body font-bold lg:mt-1 lg:text-heading-card" dir="auto">
          {action}
        </p>
      </div>
      <button
        aria-label="עדכון הפעולה הבאה"
        className="flex size-11 shrink-0 items-center justify-center rounded-control bg-cv-surface text-cv-text transition-colors hover:bg-cv-surface-muted lg:h-9.5 lg:w-auto lg:self-start lg:rounded-control-sm lg:px-3.5 lg:text-support lg:font-bold"
        onClick={onUpdate}
        type="button"
      >
        <ChevronLeft aria-hidden="true" className="size-icon-lg lg:hidden" />
        <span aria-hidden="true" className="max-lg:hidden">
          עדכון הפעולה
        </span>
      </button>
    </section>
  );
};
