import { X } from "lucide-react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";
import { routePaths } from "@/app/routePaths";
import {
  actionDescription,
  actionDestination,
  actionLabel,
  preparationResumeDestination,
} from "@/features/preparation";
import { operationTypeLabels, statusLabels } from "@/features/operations";
import { buttonClasses } from "@/ui/Button";
import { cx } from "@/ui/cx";
import { StatusBadge } from "@/ui/StatusBadge";
import { Tooltip } from "@/ui/Tooltip";
import { applicationAttention, formatApplicationDate, isNextActionOverdue } from "../model/applicationListPresentation";
import { reportedOperation } from "./ApplicationListItemActions";

/* The command opens the step where the work is done; it does not do the work. "בצע"
   promised the latter - on a row whose analysis could not run for want of a provider, it
   read as a button that would run it. */
const STEP_COMMAND = "מעבר לשלב";

interface Command {
  label: string;
  strong: boolean;
  to: string;
}

interface Heading {
  command: Command | null;
  description: string | null;
  failed: boolean;
  title: string;
}

/* What the row asks for next, in the order the reader should see it: a failed run
   first, since nothing moves until it is dealt with; then a run still going; then the
   step the server recommends; then a finished CV; and only then the reader's own
   recruitment reminder. The first that applies is the heading - the rest stays below it
   as detail, so nothing the old column showed is dropped. */
export const nextActionHeading = (item: ApplicationListItem, attentive: boolean): Heading | null => {
  const operation = reportedOperation(item);
  if (operation !== null && (operation.status === "failed" || operation.status === "interrupted")) {
    return {
      command: { label: STEP_COMMAND, strong: true, to: preparationResumeDestination(item) },
      description: null,
      failed: true,
      /* Worded as the run, like the status row on the step itself: "ניתוח המשרה · נכשלה"
         paired a masculine action with the run's feminine status, and named it differently
         from the screen it opens. */
      title: `הרצת ${operationTypeLabels[operation.operation_type]} · ${statusLabels[operation.status]}`,
    };
  }
  if (operation !== null && !isTerminalOperation(operation)) {
    return {
      command: null,
      description: null,
      failed: false,
      title: `ממתין לסיום: ${operationTypeLabels[operation.operation_type]}`,
    };
  }
  if (item.recommended_action != null) {
    return {
      command: {
        label: STEP_COMMAND,
        strong: attentive,
        to: actionDestination(item.recommended_action, item.id) ?? routePaths.application(item.id),
      },
      description: actionDescription(item.recommended_action),
      failed: false,
      title: actionLabel(item.recommended_action),
    };
  }
  if (item.latest_ready_revision_id != null) {
    return {
      command: { label: "פתיחה", strong: false, to: routePaths.revision(item.latest_ready_revision_id) },
      description: null,
      failed: false,
      title: "קורות החיים מוכנים",
    };
  }
  if (item.next_action != null) {
    return { command: null, description: null, failed: false, title: item.next_action };
  }
  return null;
};

/* The projected reasons, as a link into the screen that resolves them. When the label
   had to shorten the list ("+N נוספים"), the full list is the system tooltip; when it
   already says everything, a tooltip would only repeat it. */
export const AttentionLink = ({
  attention,
  className,
  item,
}: {
  attention: NonNullable<ReturnType<typeof applicationAttention>>;
  className?: string;
  item: ApplicationListItem;
}) => {
  const full = attention.items.map((entry) => entry.title).join(" · ");
  const link = (
    <Link
      aria-label={`${item.company}: ${full}`}
      className={cx(
        "line-clamp-2 text-support font-medium hover:underline",
        attention.tone === "blocker" ? "text-cv-blocker" : "text-cv-warning",
        className,
      )}
      to={preparationResumeDestination(item)}
    >
      <span>{attention.label}</span>
    </Link>
  );

  return full === attention.label ? (
    link
  ) : (
    <Tooltip align="center" className="min-w-0" label={full} wrap>
      {link}
    </Tooltip>
  );
};

/* The table row's next-action cell, drawn after demo_re: a title and one line of detail
   on the reading side, the command and the reminder's dismissal at the far edge. */
export const ApplicationRowNextAction = ({
  clearing,
  item,
  onClearNextAction,
}: {
  clearing: boolean;
  item: ApplicationListItem;
  onClearNextAction: (item: ApplicationListItem) => void;
}) => {
  const attention = applicationAttention(item);
  const head = nextActionHeading(item, attention !== null);

  if (head === null) {
    return <span className="text-support text-cv-text-muted">אין פעולה מתוזמנת</span>;
  }

  const reminderIsHeading = head.title === item.next_action && head.command === null;
  const overdue = !item.is_closed && isNextActionOverdue(item.next_action_date);
  const showReadyRevision = item.latest_ready_revision_id != null && head.title !== "קורות החיים מוכנים";

  return (
    <div className="flex w-full items-center gap-2">
      <div className="min-w-0 flex-1">
        <p
          className={cx("line-clamp-2 text-support font-semibold", head.failed ? "text-cv-blocker" : "text-cv-text")}
          dir="auto"
        >
          {head.title}
        </p>
        {head.description === null ? null : (
          <p className="line-clamp-2 text-support text-cv-text-muted">{head.description}</p>
        )}
        {attention === null ? null : <AttentionLink attention={attention} item={item} />}
        {item.next_action == null ? null : (
          <p className="flex flex-wrap items-center gap-1.5 text-support text-cv-text-muted">
            {overdue ? (
              <StatusBadge className="px-2 py-0" tone="warning">
                באיחור
              </StatusBadge>
            ) : null}
            {reminderIsHeading ? null : <span dir="auto">{item.next_action}</span>}
            {item.next_action_date == null ? null : (
              <span className="tabular-nums">
                {reminderIsHeading ? "" : "· "}
                {formatApplicationDate(item.next_action_date)}
              </span>
            )}
          </p>
        )}
        {showReadyRevision && item.latest_ready_revision_id != null ? (
          <Link
            className="text-support font-medium text-cv-text-muted hover:text-cv-text hover:underline"
            to={routePaths.revision(item.latest_ready_revision_id)}
          >
            הגרסה המוכנה
          </Link>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        {head.command === null ? null : (
          <Link
            aria-label={`${head.title} · ${item.company}`}
            className={buttonClasses(head.command.strong ? "primary" : "secondary", "px-3", "compact")}
            to={head.command.to}
          >
            {head.command.label}
          </Link>
        )}
        {item.next_action == null ? null : (
          <Tooltip label="הסרת התזכורת, ללא רישום השלמה">
            <button
              aria-label={`הסרת התזכורת של ${item.company}`}
              className="inline-flex size-8 items-center justify-center rounded-control text-cv-text-muted transition-colors hover:bg-cv-surface-muted hover:text-cv-text disabled:opacity-50"
              disabled={clearing}
              onClick={() => onClearNextAction(item)}
              type="button"
            >
              <X aria-hidden="true" className="size-icon-sm" />
            </button>
          </Tooltip>
        )}
      </div>
    </div>
  );
};

/* A run still going, as the demo draws it beside the recruitment status: the CV track
   is what it is changing, so the reader looks for it there. */
export const ApplicationRunningOperation = ({ item }: { item: ApplicationListItem }) => {
  const operation = reportedOperation(item);
  if (operation === null || isTerminalOperation(operation)) return null;

  return (
    <span className="inline-flex items-center gap-1.5 rounded-pill border border-cv-border px-2 py-0.5 text-support text-cv-text-muted">
      <span aria-hidden="true" className="size-1.5 shrink-0 rounded-pill bg-cv-accent motion-safe:animate-pulse" />
      {operationTypeLabels[operation.operation_type]} רצה…
    </span>
  );
};
