import type { ApplicationListItem } from "../../api/contracts";
import type { StatusTone } from "../../ui/status";

const dateFormat = new Intl.DateTimeFormat("he-IL", { dateStyle: "short" });

export const formatApplicationDate = (value: string): string => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : dateFormat.format(parsed);
};

/* This is a visual comparison against the reader's local date. It does not affect
   filtering, workflow state, or any server-side deadline decision. */
export const isNextActionOverdue = (value: string | null | undefined, today: Date = new Date()): boolean => {
  if (value == null) {
    return false;
  }

  const due = new Date(value);
  if (Number.isNaN(due.getTime())) {
    return false;
  }

  const midnight = new Date(today);
  midnight.setHours(0, 0, 0, 0);
  return due < midnight;
};

export interface ApplicationAttention {
  label: string;
  tone: StatusTone;
}

export const applicationAttention = (item: ApplicationListItem): ApplicationAttention | null => {
  const parts = [
    item.review_reasons.length === 0 ? null : `${item.review_reasons.length} להכרעה`,
    item.stale_reasons.length === 0 ? null : `${item.stale_reasons.length} לא מעודכן`,
    item.warnings.length === 0 ? null : `${item.warnings.length} אזהרות`,
  ].filter((part): part is string => part !== null);

  if (parts.length === 0) {
    return null;
  }

  const tone: StatusTone =
    item.review_reasons.length > 0
      ? "blocker"
      : item.stale_reasons.length > 0 || item.warnings.length > 0
        ? "warning"
        : "neutral";

  return { label: parts.join(" · "), tone };
};

/* Mirrors the list projection's current activity classification. A future `can_close`
   projection should replace this duplicated client-side classification. */
const closedStatuses: ReadonlySet<string> = new Set(["rejected", "withdrawn", "closed"]);

export const isApplicationClosed = (item: ApplicationListItem): boolean =>
  item.terminal_outcome != null || closedStatuses.has(item.recruitment_status);
