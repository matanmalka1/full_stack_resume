import type { ApplicationListItem } from "../../api/contracts";
import type { StatusTone } from "../../ui/status";
import { reasonTitle, warningTitle } from "../application/applicationLabels";

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

export interface AttentionItem {
  code: string;
  title: string;
}

export interface ApplicationAttention {
  /* Every title, most severe first: what the badge's `title` and `aria-label` carry. */
  items: AttentionItem[];
  /* What the badge shows: the titles themselves up to two, then the most severe one
     plus a count of what it stands in front of. */
  label: string;
  tone: StatusTone;
}

const ATTENTION_OVERFLOW_LIMIT = 2;

/* The three sources the board reports under one column, in the severity order the
   detail screen's alert region already uses: a blocker, then a draft that no longer
   matches its sources, then a note.

   The stale group is led by `primary_stale_reason`. The projection picks which of
   several stale reasons is the one to name; the board repeats that choice rather than
   re-deriving it, and the remaining reasons follow it with the primary not repeated. */
const attentionItems = (item: ApplicationListItem): AttentionItem[] => {
  const staleCodes = [
    ...(item.primary_stale_reason == null ? [] : [item.primary_stale_reason]),
    ...item.stale_reasons.map((reason) => reason.code),
  ];

  return [
    ...item.review_reasons.map((reason) => ({
      code: reason.code,
      title: reasonTitle(reason.code, "נדרשת החלטה לפני המשך"),
    })),
    ...[...new Set(staleCodes)].map((code) => ({
      code,
      title: reasonTitle(code, "הטיוטה אינה מעודכנת מול המקורות שלה"),
    })),
    ...item.warnings.map((warning) => ({
      code: warning.code,
      title: warningTitle(warning.code),
    })),
  ];
};

export const applicationAttention = (item: ApplicationListItem): ApplicationAttention | null => {
  const items = attentionItems(item);

  if (items.length === 0) {
    return null;
  }

  const label =
    items.length <= ATTENTION_OVERFLOW_LIMIT
      ? items.map((entry) => entry.title).join(" · ")
      : `${items[0].title} · +${items.length - 1} נוספים`;

  return { items, label, tone: item.review_reasons.length > 0 ? "blocker" : "warning" };
};

/* Mirrors the list projection's current activity classification. A future `can_close`
   projection should replace this duplicated client-side classification. */
const closedStatuses: ReadonlySet<string> = new Set(["rejected", "withdrawn", "closed"]);

export const isApplicationClosed = (item: ApplicationListItem): boolean =>
  item.terminal_outcome != null || closedStatuses.has(item.recruitment_status);
