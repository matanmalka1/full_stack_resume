import type { ApplicationListItem } from "../../api/contracts";
import type { StatusTone } from "../../ui/status";
import { formatDateTime } from "../../ui/formatDateTime";
import { reasonTitle, warningTitle } from "../application/applicationLabels";

export const formatApplicationDate = (value: string): string => formatDateTime(value, "date");

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

/* The posting's origin as the one word a row has space for: the host, without `www.`.
   A URL the browser cannot parse is not guessed at - the row falls back to the stored
   source name instead. */
export const sourceHost = (url: string | null | undefined): string | null => {
  if (url == null || url === "") {
    return null;
  }

  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
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
