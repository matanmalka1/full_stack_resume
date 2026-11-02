import type { ApplicationListItem, PreparationState } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";
import { routePaths } from "@/navigation/routePaths";
import { operationTypeLabels, statusLabels } from "@/features/operations";
import {
  actionLabel,
  preparationResumeDestination,
  preparationStateLabels,
  reasonTitle,
  warningTitle,
} from "@/features/preparation";
import { formatDateTime } from "@/utils/formatDateTime";

export const formatApplicationDate = (value: string): string => formatDateTime(value, "date");

const localDayNumber = (date: Date): number =>
  Math.round(new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime() / 86_400_000);

/* When an Application last changed, the way the board's card says it after "עודכן": by
   the hour today, by the reader's local calendar day for the rest of the week, then as a
   date. It is presentation only - the full date stays in the element's `dateTime` - and a
   value that does not parse, or one on a later day, falls back to the absolute form
   rather than a guessed phrase. */
export const formatRelativeUpdate = (value: string, now: Date = new Date()): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  const days = localDayNumber(now) - localDayNumber(parsed);
  if (days === 0) {
    const hours = Math.floor((now.getTime() - parsed.getTime()) / 3_600_000);
    return hours < 1 ? "עכשיו" : `לפני ${hours} שע׳`;
  }
  if (days === 1) return "אתמול";
  if (days === 2) return "לפני יומיים";
  if (days > 2 && days < 7) return `לפני ${days} ימים`;
  return `ב־${formatApplicationDate(value)}`;
};

/* Where a CV state sits along the way to Ready, for the card's step bar. The order is the
   one the specification lists the values in (§4) and the one the board's "stage" sort
   already ranks by; it is read from the exhaustive label map rather than restated, so a
   new state cannot be left out of the bar. It is a position, not a promise of forward
   motion: an edit to an approved document projects back to `draft_in_progress`. */
const preparationOrder = Object.keys(preparationStateLabels) as PreparationState[];

export const preparationProgress = (state: PreparationState): { step: number; total: number } => ({
  step: preparationOrder.indexOf(state) + 1,
  total: preparationOrder.length,
});

/* This is a visual comparison against the reader's local date. It does not affect
   filtering, workflow state, or any server-side deadline decision. */
const dateOnlyKey = (value: string | null | undefined): string | null => {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? "");
  if (match === null) {
    return null;
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];
  return daysInMonth !== undefined && day >= 1 && day <= daysInMonth ? match[0] : null;
};

const localDateKey = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

export const isNextActionOverdue = (value: string | null | undefined, today: Date = new Date()): boolean => {
  const due = dateOnlyKey(value);
  return due !== null && due < localDateKey(today);
};

export const isDueToday = (value: string | null | undefined, today: Date = new Date()): boolean =>
  dateOnlyKey(value) === localDateKey(today);

/* After today and within the six days that follow it: the rest of the reader's week. */
export const isDueThisWeek = (value: string | null | undefined, today: Date = new Date()): boolean => {
  const due = dateOnlyKey(value);
  const weekEnd = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 6);
  return due !== null && due > localDateKey(today) && due <= localDateKey(weekEnd);
};

interface ApplicationAttention {
  /* Every title, most severe first, joined - what a badge's accessible name carries. */
  label: string;
  /* The most severe one alone, for a line that has room for one. */
  title: string;
}

/* The two sources the board reports as "needs attention", in the severity order the
   detail screen's alert region already uses: a blocking review reason, then a warning.
   The same predicate the server's `needs_attention` preset answers. */
export const applicationAttention = (item: ApplicationListItem): ApplicationAttention | null => {
  const titles = [
    ...item.review_reasons.map((reason) => reasonTitle(reason.code, "נדרשת החלטה לפני המשך")),
    ...item.warnings.map((warning) => warningTitle(warning.code)),
  ];
  const first = titles[0];
  return first === undefined ? null : { label: titles.join(" · "), title: first };
};

/* Terminal only means polling may stop. A failed or interrupted run remains the most
   important next-step fact until a newer run supersedes it; successful and deliberately
   cancelled work yield back to the projection's normal recommendation. */
const reportedOperation = (item: ApplicationListItem) => {
  const latest = item.active_operation ?? item.latest_operation;

  return latest != null &&
    (!isTerminalOperation(latest) || latest.status === "failed" || latest.status === "interrupted")
    ? latest
    : null;
};

/* What a record asks for next, as one line for the details sheet: a failed run first,
   since nothing moves until it is dealt with; then a run still going; then the step the
   server recommends; then a finished CV; and only then the reader's own recruitment
   reminder. */
export const nextStepText = (item: ApplicationListItem): string | null => {
  const operation = reportedOperation(item);
  if (operation !== null && (operation.status === "failed" || operation.status === "interrupted")) {
    return `הרצת ${operationTypeLabels[operation.operation_type]} · ${statusLabels[operation.status]}`;
  }
  if (operation !== null) return `ממתין לסיום: ${operationTypeLabels[operation.operation_type]}`;
  if (item.recommended_action != null) return actionLabel(item.recommended_action);
  if (item.preparation_state === "ready") return "קורות החיים מוכנים";
  return item.next_action ?? null;
};

type HubItemType = "overdue" | "due_today" | "attention" | "due_this_week" | "ready";

export interface HubItem {
  application: ApplicationListItem;
  /* The short word on the row's badge. */
  label: string;
  title: string;
  to: string;
  type: HubItemType;
}

const hubOrder: Record<HubItemType, number> = {
  overdue: 0,
  due_today: 1,
  attention: 2,
  due_this_week: 3,
  ready: 4,
};

/* What waits on the reader across the open board, one row per Application: a reminder
   that is past its date, due today or due this week; a projected reason that needs a
   decision; a CV that is Ready to send. The most pressing source wins for an Application
   that meets several, so one record never fills the panel. The reasons and Ready come
   from the server's projection; the dates are only a local reading of a stored reminder.

   Every row is a way to where the thing is done: a reminder to the Application, where
   its status and reminder are kept; a reason to the step that resolves it; a Ready CV to
   the ready step. */
export const attentionHubItems = (items: readonly ApplicationListItem[], today: Date = new Date()): HubItem[] => {
  const hub: HubItem[] = [];

  for (const application of items) {
    if (application.is_closed) continue;

    const due = application.next_action == null ? null : application.next_action_date;
    const reminder = (type: HubItemType, label: string): HubItem => ({
      application,
      label,
      title: application.next_action ?? "",
      to: routePaths.application(application.id),
      type,
    });
    const attention = applicationAttention(application);

    if (isNextActionOverdue(due, today)) hub.push(reminder("overdue", "באיחור"));
    else if (isDueToday(due, today)) hub.push(reminder("due_today", "היום"));
    else if (attention !== null) {
      hub.push({
        application,
        label: "דורש טיפול",
        title: attention.title,
        to: preparationResumeDestination(application),
        type: "attention",
      });
    } else if (isDueThisWeek(due, today)) hub.push(reminder("due_this_week", "השבוע"));
    else if (application.preparation_state === "ready") {
      hub.push({
        application,
        label: "מוכן",
        title: "קורות החיים מוכנים לשליחה",
        to: routePaths.ready(application.id),
        type: "ready",
      });
    }
  }

  // ES2022 has no toSorted; `hub` is newly built and belongs only to this call.
  // oxlint-disable-next-line unicorn/no-array-sort
  return hub.sort(
    (left, right) =>
      hubOrder[left.type] - hubOrder[right.type] ||
      (left.application.next_action_date ?? "").localeCompare(right.application.next_action_date ?? ""),
  );
};
