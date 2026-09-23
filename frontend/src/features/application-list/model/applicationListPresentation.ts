import { routePaths } from "@/app/routePaths";
import type { ApplicationListItem, PreparationState } from "@/api/contracts";
import {
  preparationResumeDestination,
  preparationStateLabels,
  reasonTitle,
  warningTitle,
} from "@/features/preparation";
import type { Tone } from "@/ui/tone";
import { formatDateTime } from "@/utils/formatDateTime";

export const formatApplicationDate = (value: string): string => formatDateTime(value, "date");

/* Which page numbers the pager draws: the first and last, the current one and its
   neighbours, and a gap wherever pages in between are left out. A gap never stands in
   for a single page - that page is drawn instead, since a number is no wider. */
export const pageWindow = (current: number, count: number): (number | "gap")[] => {
  const shown = [...new Set([1, current - 1, current, current + 1, count])]
    .filter((page) => page >= 1 && page <= count)
    // ES2022 has no toSorted; this array is newly created and belongs only to this call.
    // oxlint-disable-next-line unicorn/no-array-sort
    .sort((left, right) => left - right);

  return shown.flatMap((page, index) => {
    const previous = shown[index - 1];
    if (previous === undefined || page - previous === 1) return [page];
    if (page - previous === 2) return [previous + 1, page];
    return ["gap" as const, page];
  });
};

const localDayNumber = (date: Date): number =>
  Math.round(new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime() / 86_400_000);

/* When an Application last changed, the way the board says it (after demo_re): by the
   hour today, by the reader's local calendar day for the rest of the week, then as a
   date. It is presentation only - the full date stays in the element's title and
   `dateTime` - and a value that does not parse, or one on a later day, falls back to the
   absolute form rather than a guessed phrase. */
export const formatRelativeUpdate = (value: string, now: Date = new Date()): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  const days = localDayNumber(now) - localDayNumber(parsed);
  if (days === 0) {
    const hours = Math.floor((now.getTime() - parsed.getTime()) / 3_600_000);
    return hours < 1 ? "עודכן עכשיו" : `עודכן היום (לפני ${hours} שע׳)`;
  }
  if (days === 1) return "עודכן אתמול";
  if (days === 2) return "עודכן לפני יומיים";
  if (days > 2 && days < 7) return `עודכן לפני ${days} ימים`;
  return formatApplicationDate(value);
};

/* Where a CV state sits along the way to Ready, for the row's step bar. The order is the
   one the specification lists the values in (§4) and the one the board's "stage" sort
   already ranks by; it is read from the exhaustive label map rather than restated, so a
   new state cannot be left out of the bar. It is a position, not a promise of forward
   motion: a stale draft that needs a decision projects back to `needs_review`. */
const preparationOrder = Object.keys(preparationStateLabels) as PreparationState[];

export const preparationProgress = (state: PreparationState): { step: number; total: number } => ({
  step: preparationOrder.indexOf(state) + 1,
  total: preparationOrder.length,
});

/* A visual hint only: records with the same company and role need their dates exposed
   so two distinct Applications do not read as one repeated row. */
export const duplicatedApplicationIdentityIds = (items: readonly ApplicationListItem[]): ReadonlySet<string> => {
  const byIdentity = new Map<string, string[]>();

  for (const item of items) {
    const key = `${item.company}\n${item.target_role}`;
    byIdentity.set(key, [...(byIdentity.get(key) ?? []), item.id]);
  }

  return new Set([...byIdentity.values()].filter((ids) => ids.length > 1).flat());
};

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
  tone: Tone;
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

type HubItemType = "attention" | "due_today" | "overdue" | "ready";

export interface HubItem {
  actionLabel: string;
  actionTo: string | null;
  application: ApplicationListItem;
  label: string;
  subtitle: string;
  title: string;
  tone: Tone;
  type: HubItemType;
}

/* This is a priority summary of the current server-projected page, not a second list
   filter. Attention comes from the projection's reason collections, Ready comes from
   its active ready revision, and the date comparison is only a local presentation of a
   stored reminder. One card per Application prevents a single row from occupying the
   entire hub when it happens to satisfy several conditions. */
export const attentionHubItems = (items: readonly ApplicationListItem[], today: Date = new Date()): HubItem[] => {
  const due: HubItem[] = [];
  const attention: HubItem[] = [];
  const ready: HubItem[] = [];

  for (const application of items) {
    if (application.is_closed) {
      continue;
    }

    const applicationHref = preparationResumeDestination(application);
    if (
      application.next_action != null &&
      application.next_action_date != null &&
      (isNextActionOverdue(application.next_action_date, today) || isDueToday(application.next_action_date, today))
    ) {
      const overdue = isNextActionOverdue(application.next_action_date, today);
      due.push({
        actionLabel: overdue ? "עדכון סטטוס ומשימה" : "פתיחת המועמדות",
        actionTo: overdue ? null : applicationHref,
        application,
        label: overdue ? "באיחור" : "להיום",
        subtitle: `${formatApplicationDate(application.next_action_date)} · ${application.target_role}`,
        title: application.next_action,
        tone: overdue ? "blocker" : "progress",
        type: overdue ? "overdue" : "due_today",
      });
      continue;
    }

    const projectedAttention = applicationAttention(application);
    if (projectedAttention != null) {
      attention.push({
        actionLabel: "פתיחת מסך ההכנה",
        actionTo: preparationResumeDestination(application),
        application,
        label: "דורש טיפול",
        subtitle: application.target_role,
        title: projectedAttention.label,
        tone: projectedAttention.tone,
        type: "attention",
      });
      continue;
    }

    if (application.latest_ready_revision_id != null) {
      ready.push({
        actionLabel: "פתיחת הגרסה המוכנה",
        actionTo: routePaths.revision(application.latest_ready_revision_id),
        application,
        label: "מוכן לשליחה",
        subtitle: application.target_role,
        title: "קורות החיים מוכנים להורדה ולהגשה",
        tone: "success",
        type: "ready",
      });
    }
  }

  due.sort((left, right) =>
    (left.application.next_action_date ?? "").localeCompare(right.application.next_action_date ?? ""),
  );
  return [...due, ...attention, ...ready].slice(0, 3);
};
