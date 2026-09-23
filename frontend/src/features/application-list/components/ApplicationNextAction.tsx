import { Clock } from "lucide-react";

import type { ApplicationListItem } from "@/api/contracts";
import { cx } from "@/ui/cx";
import type { ApplicationListViewVariant } from "../model/applicationList.types";
import { formatApplicationDate, isNextActionOverdue } from "../model/applicationListPresentation";

export const ApplicationNextAction = ({
  closed = false,
  item,
  variant,
}: {
  closed?: boolean;
  item: ApplicationListItem;
  variant: ApplicationListViewVariant;
}) => {
  if (item.next_action == null) {
    return null;
  }
  if (variant === "pipeline") {
    return (
      <p className="mt-2 line-clamp-2 rounded-control bg-cv-surface-muted px-2 py-1.5 text-support text-cv-text-muted">
        <strong className="text-cv-text">הבא: </strong>
        <span dir="auto">{item.next_action}</span>
      </p>
    );
  }

  const overdue = !closed && isNextActionOverdue(item.next_action_date);
  return (
    <div
      className={cx(
        "mb-3 rounded-control border px-3 py-2 text-support",
        overdue
          ? "border-cv-blocker/30 bg-cv-blocker-soft text-cv-blocker"
          : "border-cv-border bg-cv-surface-muted text-cv-text",
      )}
    >
      <div className="mb-1 flex items-center justify-between gap-2 font-semibold">
        <span className="inline-flex items-center gap-1.5 text-cv-text-muted">
          <Clock aria-hidden="true" className="size-icon-sm text-cv-accent" />
          הצעד הבא
        </span>
        {item.next_action_date == null ? null : (
          <span className="whitespace-nowrap text-cv-text-muted">
            {formatApplicationDate(item.next_action_date)}
            {overdue ? " · באיחור" : null}
          </span>
        )}
      </div>
      <p className="line-clamp-2 font-semibold" dir="auto">
        {item.next_action}
      </p>
    </div>
  );
};
